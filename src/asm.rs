use std::ffi::{OsStr, OsString};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use regex::Regex;
use sha1::{Digest, Sha1};

use crate::manifest::Manifest;
use crate::plan::{Plan, assembly_object, link_object, listing_wrapper_reason, selected_object};
use crate::process;

fn os(value: impl AsRef<OsStr>) -> OsString {
    value.as_ref().to_owned()
}

pub fn compile(
    root: &Path,
    manifest: &Manifest,
    source: &Path,
    expected_asm: &Path,
    output: &Path,
) -> Result<()> {
    let source = root.join(source);
    if let Some(reason) = listing_wrapper_reason(&source)? {
        bail!(reason);
    }
    let output = absolute_output(output)?;
    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent)?;
    }
    let temp = tempfile::tempdir_in(output.parent().unwrap_or(root))?;
    let preprocessed = temp.path().join("source.i");
    let generated_asm = temp.path().join("source.s");
    let tc = &manifest.toolchain;
    let mut cpp_args = vec![
        os("-P"),
        os("-I"),
        os(root.join("include")),
        os("-I"),
        os(source.parent().unwrap_or(root)),
    ];
    if let Some(psyq) = psyq_include(root) {
        cpp_args.extend([os("-I"), os(psyq)]);
    }
    cpp_args.extend([os(&source), os("-o"), os(&preprocessed)]);
    process::run(&tc.cpp, &cpp_args, root)?;

    let mut cc_args = vec![os("-quiet")];
    cc_args.extend(tc.c_args.iter().map(os));
    cc_args.extend([os("-o"), os(&generated_asm), os(&preprocessed)]);
    process::run(&tc.cc1, &cc_args, root)?;

    let mut maspsx_args = vec![
        os(format!("--aspsx-version={}", tc.aspsx_version)),
        os("--run-assembler"),
        os(format!("--gnu-as-path={}", tc.assembler)),
    ];
    maspsx_args.extend(tc.assembler_args.iter().map(os));
    maspsx_args.extend([
        os("-I"),
        os(root.join("include")),
        os("-I"),
        os(root),
        os("-o"),
        os(&output),
        os(&generated_asm),
    ]);
    process::run(&tc.maspsx, &maspsx_args, root)?;

    let expected_asm = root.join(expected_asm);
    let expected_size = expected_text_size(&expected_asm)?;
    let actual_size = elf_section_size(&output, ".text")?;
    if actual_size < expected_size
        && append_trailing_padding(&expected_asm, &generated_asm, expected_size - actual_size)?
    {
        process::run(&tc.maspsx, &maspsx_args, root)?;
    }
    Ok(())
}

fn expected_text_size(expected: &Path) -> Result<u64> {
    let encoded = Regex::new(r"^\s*/\*[^*]+\*/\s+.+$")?;
    Ok(fs::read_to_string(expected)?
        .lines()
        .filter(|line| encoded.is_match(line))
        .count() as u64
        * 4)
}

fn append_trailing_padding(expected: &Path, generated: &Path, bytes: u64) -> Result<bool> {
    if bytes == 0 || !bytes.is_multiple_of(4) {
        return Ok(false);
    }
    let text = fs::read_to_string(expected)?;
    let symbol = expected
        .file_stem()
        .and_then(OsStr::to_str)
        .context("expected assembly has no UTF-8 filename")?;
    let end = format!("endlabel {symbol}");
    let end_data = format!("enddlabel {symbol}");
    let mut after_end = false;
    let encoded = Regex::new(r"^\s*/\*[^*]+\*/\s+.+$")?;
    let mut padding = Vec::new();
    for line in text.lines() {
        if line.trim() == end || line.trim() == end_data {
            after_end = true;
            continue;
        }
        if after_end && encoded.is_match(line) {
            padding.push(line);
        }
    }
    let words = (bytes / 4) as usize;
    if padding.len() >= words {
        let mut file = OpenOptions::new().append(true).open(generated)?;
        writeln!(file, ".section .text, \"ax\"")?;
        for line in padding.into_iter().take(words) {
            writeln!(file, "{line}")?;
        }
        return Ok(true);
    }
    Ok(false)
}

fn elf_section_size(path: &Path, section: &str) -> Result<u64> {
    let bytes = fs::read(path)?;
    if bytes.get(0..4) != Some(b"\x7fELF") || bytes.get(4) != Some(&1) || bytes.get(5) != Some(&1) {
        bail!("{} is not a little-endian ELF32 object", path.display());
    }
    let u16_at = |offset: usize| -> Result<usize> {
        Ok(u16::from_le_bytes(
            bytes
                .get(offset..offset + 2)
                .context("truncated ELF header")?
                .try_into()?,
        ) as usize)
    };
    let u32_at = |offset: usize| -> Result<usize> {
        Ok(u32::from_le_bytes(
            bytes
                .get(offset..offset + 4)
                .context("truncated ELF data")?
                .try_into()?,
        ) as usize)
    };
    let table = u32_at(32)?;
    let entry_size = u16_at(46)?;
    let count = u16_at(48)?;
    let names_index = u16_at(50)?;
    let names_header = table + names_index * entry_size;
    let names_offset = u32_at(names_header + 16)?;
    let names_size = u32_at(names_header + 20)?;
    let names = bytes
        .get(names_offset..names_offset + names_size)
        .context("truncated ELF section names")?;
    for index in 0..count {
        let header = table + index * entry_size;
        let name_offset = u32_at(header)?;
        let name = names
            .get(name_offset..)
            .and_then(|tail| tail.split(|byte| *byte == 0).next())
            .context("invalid ELF section name")?;
        if name == section.as_bytes() {
            return Ok(u32_at(header + 20)? as u64);
        }
    }
    bail!("{} has no {section} section", path.display())
}

pub fn assemble(
    root: &Path,
    manifest: &Manifest,
    source: &Path,
    output: &Path,
    export_locals: bool,
) -> Result<()> {
    let source = root.join(source);
    let output = absolute_output(output)?;
    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent)?;
    }
    let staged = is_function_assembly(&source)
        .then(|| stage_function_assembly(&source, output.parent().unwrap_or(root), export_locals))
        .transpose()?;
    let assembly = staged
        .as_ref()
        .map_or(source.as_path(), tempfile::NamedTempFile::path);
    let mut args: Vec<OsString> = manifest.toolchain.assembler_args.iter().map(os).collect();
    args.extend([
        os("-I"),
        os(root.join("include")),
        os("-I"),
        os(root),
        os("-o"),
        os(&output),
        os(assembly),
    ]);
    process::run(&manifest.toolchain.assembler, &args, root)
}

pub fn select(
    root: &Path,
    symbol: &str,
    expected: &Path,
    fallback: &Path,
    candidate: &Path,
    output: &Path,
) -> Result<()> {
    let expected = absolute_output(expected)?;
    let fallback = absolute_output(fallback)?;
    let candidate = absolute_output(candidate)?;
    let output = absolute_output(output)?;
    let diff = process::capture(
        "objdiff-cli",
        &[
            os("diff"),
            os("-1"),
            os(&candidate),
            os("-2"),
            os(&expected),
            os("-o"),
            os("-"),
            os("--format"),
            os("json"),
            os("-c"),
            os("function_reloc_diffs=none"),
            os(symbol),
        ],
        root,
    )?;
    let value: serde_json::Value = serde_json::from_slice(&diff)?;
    let matched = value["left"]["symbols"]
        .as_array()
        .into_iter()
        .flatten()
        .any(|entry| {
            entry["name"] == symbol
                && entry["match_percent"]
                    .as_f64()
                    .is_some_and(|percent| percent == 100.0)
        });
    fs::copy(if matched { &candidate } else { &fallback }, &output)?;
    println!(
        "{symbol}: {}",
        if matched { "matched C" } else { "assembly" }
    );
    Ok(())
}

fn is_function_assembly(source: &Path) -> bool {
    source
        .components()
        .any(|part| part.as_os_str() == "nonmatchings" || part.as_os_str() == "matchings")
}

fn stage_function_assembly(
    source: &Path,
    directory: &Path,
    export_locals: bool,
) -> Result<tempfile::NamedTempFile> {
    let symbol = source
        .file_stem()
        .and_then(OsStr::to_str)
        .context("function assembly has no UTF-8 filename")?;
    let label = Regex::new(r"^(?:glabel|alabel|dlabel)\s+(\S+)\s*$")?;
    let stop = Regex::new(r"^(?:glabel|alabel|dlabel|nonmatching)\s+")?;
    let text = fs::read_to_string(source)?;
    let lines: Vec<_> = text.lines().collect();
    let start = lines
        .iter()
        .position(|line| {
            label
                .captures(line)
                .is_some_and(|captures| &captures[1] == symbol)
        })
        .with_context(|| format!("{} does not define {symbol}", source.display()))?;
    let body = lines[start + 1..]
        .iter()
        .take_while(|line| !stop.is_match(line))
        .copied()
        .collect::<Vec<_>>();
    if body.is_empty() {
        bail!("{} has no assembly body for {symbol}", source.display());
    }

    let mut staged = tempfile::NamedTempFile::new_in(directory)?;
    writeln!(staged, ".include \"macro.inc\"")?;
    writeln!(staged, ".set noat")?;
    writeln!(staged, ".set noreorder")?;
    writeln!(staged, ".section .text, \"ax\"")?;
    writeln!(staged, ".globl {symbol}")?;
    writeln!(staged, "{symbol}:")?;
    let local_label = Regex::new(r"^\s*(\.L[0-9A-Fa-f]+):")?;
    for line in body {
        if line.trim_start().starts_with("endlabel ") || line.trim_start().starts_with("enddlabel ")
        {
            if !export_locals {
                break;
            }
            continue;
        }
        if export_locals && let Some(captures) = local_label.captures(line) {
            writeln!(staged, ".globl {}", &captures[1])?;
        }
        writeln!(staged, "{line}")?;
    }
    Ok(staged)
}

fn psyq_include(root: &Path) -> Option<PathBuf> {
    let local = root.join("tools/psyq/include");
    if local.is_dir() {
        return Some(local);
    }
    std::env::var_os("PSXDECOMP_PSYQ_INCLUDE")
        .map(PathBuf::from)
        .filter(|p| p.is_dir())
}

fn absolute_output(path: &Path) -> Result<PathBuf> {
    if path.is_absolute() {
        return Ok(path.to_owned());
    }
    Ok(std::env::current_dir()?.join(path))
}

pub fn link(
    root: &Path,
    manifest: &Manifest,
    plan: &Plan,
    build_dir: &Path,
    binary_id: &str,
    elf: &Path,
    raw: &Path,
) -> Result<()> {
    let binary = manifest.binary(binary_id)?;
    let elf = absolute_output(elf)?;
    let raw = absolute_output(raw)?;
    let template_path = root.join(&binary.linker_template);
    let template = fs::read_to_string(&template_path)?;
    let script = rewrite_linker_script(root, plan, build_dir, binary_id, &binary.tu, &template)?;
    let temp = tempfile::NamedTempFile::new_in(build_dir)?;
    fs::write(temp.path(), script)?;

    let mut args: Vec<OsString> = manifest.toolchain.linker_args.iter().map(os).collect();
    args.extend(defsyms(root)?);
    for name in [
        format!("undefined_syms_auto_{binary_id}.txt"),
        format!("undefined_funcs_auto_{binary_id}.txt"),
        "undefined_syms_auto.txt".into(),
        "undefined_funcs_auto.txt".into(),
    ] {
        let path = root.join("config").join(name);
        if path.is_file() && path.metadata()?.len() > 0 {
            args.extend([os("-T"), os(path)]);
        }
    }
    args.extend([os("-T"), os(temp.path()), os("-o"), os(&elf)]);
    process::run(&manifest.toolchain.linker, &args, root)?;
    process::run(
        &manifest.toolchain.objcopy,
        &[os("-O"), os("binary"), os(&elf), os(&raw)],
        root,
    )?;
    let mut bytes = fs::read(&raw)?;
    if bytes.len() > binary.size as usize {
        bail!(
            "{} linked to {} bytes, expected {}",
            binary.id,
            bytes.len(),
            binary.size
        );
    }
    bytes.resize(binary.size as usize, 0);
    fs::write(&raw, bytes)?;
    Ok(())
}

fn rewrite_linker_script(
    root: &Path,
    plan: &Plan,
    build_dir: &Path,
    binary: &str,
    tu: &str,
    template: &str,
) -> Result<String> {
    let functions: Vec<_> = plan
        .functions
        .iter()
        .filter(|f| f.binary == binary)
        .collect();
    let assemblies: Vec<_> = plan
        .assembly
        .iter()
        .filter(|a| a.binary == binary)
        .collect();
    let tu_marker = format!("/src/{binary}/{tu}.o(");
    let mut out = String::new();
    for line in template.lines() {
        if let Some(section) = line
            .split(&tu_marker)
            .nth(1)
            .and_then(|v| v.strip_suffix(");"))
        {
            let indent = line
                .chars()
                .take_while(|c| c.is_whitespace())
                .collect::<String>();
            for function in &functions {
                let name = if function.source.is_some() {
                    selected_object(binary, &function.symbol)
                } else {
                    link_object(binary, &function.symbol)
                };
                out.push_str(&format!(
                    "{indent}{}({section});\n",
                    build_dir.join(name).display()
                ));
            }
            continue;
        }
        if line.contains(&format!("build/{binary}/asm/{binary}/")) && line.contains(".o(") {
            let section = line.split(".o(").nth(1).and_then(|v| v.strip_suffix(");"));
            let object_fragment = line.split_whitespace().find(|v| v.contains(".o("));
            if let (Some(section), Some(fragment)) = (section, object_fragment) {
                let before = fragment.split(".o(").next().unwrap_or_default();
                let rel_after = before
                    .split(&format!("build/{binary}/asm/{binary}/"))
                    .nth(1);
                if let Some(rel_after) = rel_after {
                    let source = PathBuf::from("asm")
                        .join(binary)
                        .join(format!("{rel_after}.s"));
                    if let Some(found) = assemblies.iter().find(|a| a.source == source) {
                        let indent = line
                            .chars()
                            .take_while(|c| c.is_whitespace())
                            .collect::<String>();
                        out.push_str(&format!(
                            "{indent}{}({section});\n",
                            build_dir
                                .join(assembly_object(binary, &found.source))
                                .display()
                        ));
                        continue;
                    }
                }
            }
        }
        out.push_str(line);
        out.push('\n');
    }
    if out.contains(&tu_marker) || out.contains(&format!("build/{binary}/asm/{binary}/")) {
        bail!(
            "failed to rewrite all object paths in {} linker template",
            binary
        );
    }
    let _ = root;
    Ok(out)
}

fn defsyms(root: &Path) -> Result<Vec<OsString>> {
    let path = root.join("config/symbol_addrs.txt");
    if !path.is_file() {
        return Ok(vec![]);
    }
    let mut args = Vec::new();
    for raw in fs::read_to_string(path)?.lines() {
        let (line, comment) = raw.split_once("//").unwrap_or((raw, ""));
        if !comment.replace(' ', "").contains("absolute:True") {
            continue;
        }
        let Some((name, rhs)) = line.split_once('=') else {
            continue;
        };
        let addr = rhs.split(';').next().unwrap_or_default().trim();
        args.extend([os("--defsym"), os(format!("{}={addr}", name.trim()))]);
    }
    Ok(args)
}

pub fn verify(manifest: &Manifest, binary_id: &str, input: &Path, stamp: &Path) -> Result<()> {
    let binary = manifest.binary(binary_id)?;
    let bytes = fs::read(input).with_context(|| format!("read {}", input.display()))?;
    if bytes.len() as u64 != binary.size {
        bail!(
            "{} has {} bytes, expected {}",
            binary.id,
            bytes.len(),
            binary.size
        );
    }
    let actual = format!("{:x}", Sha1::digest(&bytes));
    if !actual.eq_ignore_ascii_case(&binary.sha1) {
        bail!(
            "{} SHA-1 mismatch: got {}, expected {}",
            binary.id,
            actual,
            binary.sha1
        );
    }
    fs::write(stamp, format!("{}  {}\n", actual, binary.name))?;
    println!("{}: verified", binary.name);
    Ok(())
}
