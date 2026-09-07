use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use anyhow::{Context, Result, bail};
use regex::{Captures, Regex};
use sha1::{Digest, Sha1};

use crate::manifest::{BinaryKind, Manifest};
use crate::plan::normalize_symbol;
use crate::process;

const ADDIU_SP: u32 = 0x27BD_0000;
const JR_RA: u32 = 0x03E0_0008;
const PROLOGUE_GAP: usize = 0x4000;
const EPILOGUE_WINDOW: usize = 0x8000;

pub fn run(root: &Path, manifest: &Manifest) -> Result<()> {
    let state = root.join(".devenv/state");
    fs::create_dir_all(&state)?;
    let stage = tempfile::tempdir_in(&state)?;
    let staged = stage.path();
    link_game(root, staged)?;
    copy_curated(root, staged, manifest)?;
    generate_configs(staged, manifest)?;

    for binary in &manifest.binary {
        let config = staged.join(&binary.splat_config);
        process::run(
            "splat",
            &["split".into(), config.as_os_str().into()],
            staged,
        )
        .with_context(|| format!("split {}", binary.id))?;
    }
    patch_generated(staged, manifest)?;
    prepare_composite_dirs(root, staged, manifest)?;
    promote(root, staged)?;
    println!("regenerated {} binaries", manifest.binary.len());
    Ok(())
}

#[cfg(unix)]
fn link_game(root: &Path, stage: &Path) -> Result<()> {
    std::os::unix::fs::symlink(root.join("game"), stage.join("game"))?;
    Ok(())
}

fn copy_curated(root: &Path, stage: &Path, manifest: &Manifest) -> Result<()> {
    fs::create_dir_all(stage.join("config"))?;
    for name in ["symbol_addrs.txt", "reloc_addrs.txt"] {
        let source = root.join("config").join(name);
        let target = stage.join("config").join(name);
        if source.is_file() {
            fs::copy(source, target)?;
        } else {
            fs::write(target, "")?;
        }
    }
    let source_root = root.join("src");
    if source_root.is_dir() {
        for entry in walkdir::WalkDir::new(&source_root) {
            let entry = entry?;
            if !entry.file_type().is_file() {
                continue;
            }
            let rel = entry.path().strip_prefix(root)?;
            let is_tu = manifest
                .binary
                .iter()
                .any(|b| rel == Path::new("src").join(&b.id).join(format!("{}.c", b.tu)));
            if is_tu {
                continue;
            }
            let target = stage.join(rel);
            fs::create_dir_all(target.parent().unwrap())?;
            fs::copy(entry.path(), target)?;
        }
    }
    Ok(())
}

#[derive(Debug, Clone)]
struct Overlay {
    name: String,
    load: u32,
}

fn overlays(game: &Path) -> Result<Vec<Overlay>> {
    let data = fs::read(game.join("OVERLAY.DAT"))?;
    let mut out = Vec::new();
    for record in data.chunks(0x30) {
        if record.len() < 0x30 || record[0] == 0 {
            break;
        }
        let end = record[..16].iter().position(|b| *b == 0).unwrap_or(16);
        let raw = String::from_utf8_lossy(&record[..end]).replace('\\', "/");
        let name = raw
            .rsplit('/')
            .next()
            .unwrap_or("")
            .split(';')
            .next()
            .unwrap_or("")
            .to_owned();
        if name.is_empty() {
            continue;
        }
        let load = u32::from_le_bytes(record[0x20..0x24].try_into().unwrap());
        if game.join(&name).is_file() {
            out.push(Overlay { name, load });
        }
    }
    Ok(out)
}

fn generate_configs(stage: &Path, manifest: &Manifest) -> Result<()> {
    let game = stage.join("game");
    let overlay_list = overlays(&game).unwrap_or_default();
    let mut loads: BTreeMap<u32, usize> = BTreeMap::new();
    for overlay in &overlay_list {
        *loads.entry(overlay.load).or_default() += 1;
    }
    for binary in &manifest.binary {
        let target = game.join(&binary.name);
        let data = fs::read(&target).with_context(|| format!("read {}", target.display()))?;
        let actual = format!("{:x}", Sha1::digest(&data));
        if actual != binary.sha1 || data.len() as u64 != binary.size {
            bail!("{} does not match manifest size/hash", binary.name);
        }
        let yaml = match binary.kind {
            BinaryKind::Executable => executable_yaml(binary, &data)?,
            BinaryKind::Overlay => {
                let overlay = overlay_list
                    .iter()
                    .find(|o| o.name.eq_ignore_ascii_case(&binary.name))
                    .with_context(|| format!("{} missing from OVERLAY.DAT", binary.name))?;
                overlay_yaml(
                    binary,
                    &data,
                    overlay.load,
                    loads.get(&overlay.load).copied().unwrap_or(0) > 1,
                )
            }
        };
        let path = stage.join(&binary.splat_config);
        fs::create_dir_all(path.parent().unwrap())?;
        fs::write(path, yaml)?;
    }
    Ok(())
}

fn common_yaml(name: &str, id: &str, sha1: &str, gp: u32) -> String {
    format!(
        r#"name: {name}
sha1: {sha1}
options:
  basename: {id}
  target_path: game/{name}
  elf_path: build/{id}.elf
  base_path: ..
  platform: psx
  compiler: PSYQ
  asm_path: asm/{id}
  src_path: src/{id}
  build_path: build/{id}
  ld_script_path: build/{id}.ld
  ld_dependencies: True
  find_file_boundaries: True
  o_as_suffix: True
  use_legacy_include_asm: False
  include_asm_macro_style: default
  create_c_files: True
  migrate_rodata_to_functions: False
  ld_align_section_vram_end: False
  ld_align_segment_vram_end: False
  section_order: [".rodata", ".text", ".data", ".bss"]
  ld_bss_is_noload: False
  symbol_addrs_path:
    - config/symbol_addrs.txt
  reloc_addrs_path:
    - config/reloc_addrs.txt
  undefined_funcs_auto_path: config/undefined_funcs_auto_{id}.txt
  undefined_syms_auto_path: config/undefined_syms_auto_{id}.txt
  subalign: 4
  string_encoding: ASCII
  data_string_encoding: ASCII
  gp_value: {gp:#x}
"#
    )
}

fn executable_yaml(binary: &crate::manifest::Binary, data: &[u8]) -> Result<String> {
    if data.len() < 0x800 || &data[..8] != b"PS-X EXE" {
        bail!("{} is not a PS-X EXE", binary.name);
    }
    let word = |off: usize| u32::from_le_bytes(data[off..off + 4].try_into().unwrap());
    let gp = word(0x14);
    let dest = word(0x18);
    let text_size = word(0x1c) as usize;
    let b_addr = word(0x28);
    let b_size = word(0x2c);
    let end = 0x800 + text_size;
    if end > data.len() {
        bail!("{} text size exceeds file", binary.name);
    }
    let mut yaml = common_yaml(&binary.name, &binary.id, &binary.sha1, gp);
    yaml.push_str(&format!("segments:\n  - name: header\n    type: header\n    start: 0x0\n  - name: main\n    type: code\n    start: 0x800\n    vram: 0x{dest:08X}\n    align: 4\n    subsegments:\n"));
    yaml.push_str(&format_subsegments(0x800, &data[0x800..end], &binary.tu));
    if b_size != 0 {
        let bss_vram = if b_addr != 0 {
            b_addr
        } else {
            dest + text_size as u32
        };
        yaml.push_str(&format!(
            "      - {{ start: {end:#x}, type: bss, vram: 0x{bss_vram:08X}, name: bss }}\n"
        ));
    }
    yaml.push_str(&format!("  - [{end:#x}]\n"));
    Ok(yaml)
}

fn overlay_yaml(binary: &crate::manifest::Binary, data: &[u8], load: u32, shared: bool) -> String {
    let mut yaml = common_yaml(&binary.name, &binary.id, &binary.sha1, 0);
    yaml.push_str(&format!("segments:\n  - name: {}\n    type: code\n    start: 0x0\n    vram: 0x{load:08X}\n    align: 4\n", binary.id));
    if shared {
        yaml.push_str(&format!("    exclusive_ram_id: vram_{load:08x}\n"));
    }
    yaml.push_str("    subsegments:\n");
    yaml.push_str(&format_subsegments(0, data, &binary.tu));
    yaml.push_str(&format!("  - [{:#x}]\n", data.len()));
    yaml
}

pub fn find_text_range(payload: &[u8]) -> Option<(usize, usize)> {
    if payload.len() < 16 {
        return None;
    }
    let words = payload
        .chunks_exact(4)
        .enumerate()
        .map(|(i, b)| (i * 4, u32::from_le_bytes(b.try_into().unwrap())));
    let prologues: Vec<_> = words
        .filter(|(_, w)| w & 0xffff_0000 == ADDIU_SP && w & 0x8000 != 0)
        .map(|(o, _)| o)
        .collect();
    if prologues.len() < 2 {
        return None;
    }
    let mut best_s = prologues[0];
    let mut best_e = prologues[0];
    let mut run_s = prologues[0];
    let mut prev = prologues[0];
    for &p in &prologues[1..] {
        if p - prev <= PROLOGUE_GAP {
            prev = p;
            if prev - run_s > best_e - best_s {
                best_s = run_s;
                best_e = prev;
            }
        } else {
            run_s = p;
            prev = p;
        }
    }
    let mut end = best_e + 4;
    let limit = payload.len().min(best_e + EPILOGUE_WINDOW);
    for off in (best_e..limit.saturating_sub(3)).step_by(4) {
        if u32::from_le_bytes(payload[off..off + 4].try_into().unwrap()) == JR_RA {
            end = off + 8;
        }
    }
    let mut start = best_s;
    while start >= 8
        && u32::from_le_bytes(payload[start - 8..start - 4].try_into().unwrap()) == JR_RA
    {
        start -= 8;
    }
    start &= !3;
    end = payload.len().min((end + 3) & !3);
    (end > start).then_some((start, end))
}

fn format_subsegments(file_start: usize, payload: &[u8], tu: &str) -> String {
    let Some((text_start, text_end)) = find_text_range(payload) else {
        return format!("      - [{file_start:#x}, c, {tu}]\n");
    };
    let mut out = String::new();
    if text_start > 0 {
        out.push_str(&format!("      - [{file_start:#x}, rodata, rodata]\n"));
    }
    out.push_str(&format!(
        "      - [{:#x}, c, {tu}]\n",
        file_start + text_start
    ));
    if text_end < payload.len() {
        out.push_str(&format!(
            "      - [{:#x}, data, data]\n",
            file_start + text_end
        ));
    }
    out
}

fn patch_generated(stage: &Path, manifest: &Manifest) -> Result<()> {
    fix_asm_tree(&stage.join("asm"))?;
    let include_re = Regex::new(r#"(INCLUDE_(?:ASM|RODATA)\(")([^"]+)(")"#)?;
    let stmt_re = Regex::new(r#"INCLUDE_ASM\("[^"]+",\s*([A-Za-z0-9_]+)\)\s*;"#)?;
    for binary in &manifest.binary {
        let tu = stage
            .join("src")
            .join(&binary.id)
            .join(format!("{}.c", binary.tu));
        let original = fs::read_to_string(&tu)?;
        let relative = include_re.replace_all(&original, |caps: &Captures| {
            let folder = Path::new(&caps[2]);
            let value = folder
                .strip_prefix(stage)
                .unwrap_or(folder)
                .to_string_lossy();
            format!("{}{}{}", &caps[1], value, &caps[3])
        });
        let source_dir = tu.parent().unwrap();
        let updated = stmt_re.replace_all(&relative, |caps: &Captures| {
            let wanted = &caps[1];
            let exact = source_dir.join(format!("{wanted}.c"));
            let found = if exact.is_file() {
                Some(exact)
            } else {
                fs::read_dir(source_dir).ok().and_then(|entries| {
                    entries.flatten().map(|e| e.path()).find(|p| {
                        p.extension().is_some_and(|x| x == "c")
                            && p != &tu
                            && normalize_symbol(
                                p.file_stem().unwrap_or_default().to_string_lossy().as_ref(),
                            ) == normalize_symbol(wanted)
                    })
                })
            };
            found
                .map(|p| format!("#include \"{}\"", p.file_name().unwrap().to_string_lossy()))
                .unwrap_or_else(|| caps[0].to_owned())
        });
        fs::write(tu, updated.as_bytes())?;
    }
    for entry in walkdir::WalkDir::new(stage.join("include")) {
        let entry = entry?;
        if !entry.file_type().is_file() {
            continue;
        }
        let text = fs::read_to_string(entry.path()).unwrap_or_default();
        let replaced = text.replace(stage.to_string_lossy().as_ref(), ".");
        if text != replaced {
            fs::write(entry.path(), replaced)?;
        }
    }
    Ok(())
}

fn fix_asm_tree(asm: &Path) -> Result<()> {
    if !asm.is_dir() {
        return Ok(());
    }
    let subdirs: Vec<_> = fs::read_dir(asm)?
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect();
    if subdirs.is_empty() {
        return fix_asm_subtree(asm);
    }
    for subdir in subdirs {
        fix_asm_subtree(&subdir)?;
    }
    Ok(())
}

fn fix_asm_subtree(asm: &Path) -> Result<()> {
    let label_ref = Regex::new(r"(?P<label>\.L[0-9A-Fa-f]{8})\b")?;
    let label_def = Regex::new(r"^\s*(?P<label>\.L[0-9A-Fa-f]{8})\s*:")?;
    let vram = Regex::new(r"/\*\s*[0-9A-Fa-f]+\s+(?P<vram>[0-9A-Fa-f]{8})\b")?;
    let function_def =
        Regex::new(r"^(?:glabel|alabel)\s+(?P<name>(?:fun|func|FUN|FUNC)_[0-9A-Fa-f]{8})\s*$")?;
    let data_def = Regex::new(r"^\s*dlabel\s+D_(?P<vram>[0-9A-Fa-f]{8})\s*$")?;
    let data_ref = Regex::new(r"\bD_(?P<vram>[0-9A-Fa-f]{8})\b")?;
    let files: Vec<_> = walkdir::WalkDir::new(asm)
        .sort_by_file_name()
        .into_iter()
        .collect::<std::result::Result<Vec<_>, _>>()?
        .into_iter()
        .filter(|entry| {
            entry.file_type().is_file() && entry.path().extension().is_some_and(|x| x == "s")
        })
        .map(|entry| entry.into_path())
        .collect();
    let mut functions = BTreeMap::new();
    let mut data_symbols = BTreeSet::new();
    for path in &files {
        let text = fs::read_to_string(path)?;
        for line in text.lines() {
            if let Some(caps) = function_def.captures(line) {
                let name = caps["name"].to_owned();
                let address = name.rsplit('_').next().unwrap().to_ascii_uppercase();
                functions.insert(address, name);
            }
            if let Some(caps) = data_def.captures(line) {
                data_symbols.insert(caps["vram"].to_ascii_uppercase());
            }
        }
    }
    for path in files {
        let original = fs::read_to_string(&path)?;
        let referenced: BTreeSet<_> = label_ref
            .captures_iter(&original)
            .map(|c| c["label"].to_ascii_uppercase())
            .collect();
        let defined: BTreeSet<_> = original
            .lines()
            .filter_map(|l| {
                label_def
                    .captures(l)
                    .map(|c| c["label"].to_ascii_uppercase())
            })
            .collect();
        let missing: BTreeSet<_> = referenced.difference(&defined).cloned().collect();
        let mut lines: Vec<String> = original.lines().map(|l| format!("{l}\n")).collect();
        let mut inserts = BTreeMap::new();
        for (index, line) in lines.iter().enumerate() {
            if let Some(caps) = vram.captures(line) {
                let name = format!(".L{}", caps["vram"].to_ascii_uppercase());
                if missing.contains(&name) {
                    inserts.entry(name).or_insert(index);
                }
            }
        }
        let mut inserts: Vec<_> = inserts
            .into_iter()
            .map(|(name, index)| (index, name))
            .collect();
        inserts.sort_by_key(|(index, _)| *index);
        for (index, name) in inserts.into_iter().rev() {
            lines.insert(index, format!("{name}:\n"));
        }
        let with_labels = lines.concat();
        let updated = data_ref.replace_all(&with_labels, |caps: &Captures| {
            let address = caps["vram"].to_ascii_uppercase();
            if data_symbols.contains(&address) {
                caps[0].to_owned()
            } else {
                functions
                    .get(&address)
                    .cloned()
                    .unwrap_or_else(|| caps[0].to_owned())
            }
        });
        if updated != original {
            fs::write(path, updated.as_bytes())?;
        }
    }
    Ok(())
}

fn prepare_composite_dirs(root: &Path, stage: &Path, manifest: &Manifest) -> Result<()> {
    let composite = stage.join("composite");
    fs::create_dir_all(&composite)?;
    for name in ["config", "include"] {
        copy_tree(&root.join(name), &composite.join(name))?;
    }
    let config = composite.join("config");
    for binary in &manifest.binary {
        let target = config.join(binary.splat_config.file_name().unwrap());
        fs::copy(stage.join(&binary.splat_config), target)?;
    }
    for entry in fs::read_dir(&config)? {
        let path = entry?.path();
        let name = path.file_name().unwrap().to_string_lossy();
        if name.starts_with("undefined_") && name.ends_with(".txt") {
            fs::remove_file(path)?;
        }
    }
    for entry in fs::read_dir(stage.join("config"))? {
        let path = entry?.path();
        let name = path.file_name().unwrap().to_string_lossy();
        if name.starts_with("undefined_") && name.ends_with(".txt") {
            fs::copy(&path, config.join(name.as_ref()))?;
        }
    }
    let include = composite.join("include");
    for name in ["include_asm.h", "macro.inc", "labels.inc", "gte_macros.inc"] {
        let source = stage.join("include").join(name);
        if source.is_file() {
            fs::copy(source, include.join(name))?;
        }
    }
    fs::rename(composite.join("config"), stage.join("config-final"))?;
    fs::rename(composite.join("include"), stage.join("include-final"))?;
    let build_final = stage.join("build-final");
    fs::create_dir_all(&build_final)?;
    for binary in &manifest.binary {
        fs::copy(
            stage.join("build").join(format!("{}.ld", binary.id)),
            build_final.join(format!("{}.ld", binary.id)),
        )?;
    }
    Ok(())
}

fn copy_tree(source: &Path, target: &Path) -> Result<()> {
    if !source.exists() {
        fs::create_dir_all(target)?;
        return Ok(());
    }
    for entry in walkdir::WalkDir::new(source) {
        let entry = entry?;
        let rel = entry.path().strip_prefix(source)?;
        let dest = target.join(rel);
        if entry.file_type().is_dir() {
            fs::create_dir_all(dest)?;
        } else if entry.file_type().is_file() {
            fs::create_dir_all(dest.parent().unwrap())?;
            fs::copy(entry.path(), dest)?;
        }
    }
    Ok(())
}

fn promote(root: &Path, stage: &Path) -> Result<()> {
    let backup = tempfile::tempdir_in(root.parent().unwrap_or(root))?;
    let pairs = [
        ("asm", "asm"),
        ("src", "src"),
        ("config-final", "config"),
        ("include-final", "include"),
        ("build-final", "build"),
    ];
    let mut replaced = Vec::new();
    for (staged_name, root_name) in pairs {
        let current = root.join(root_name);
        let saved = backup.path().join(root_name);
        if current.exists() {
            fs::rename(&current, &saved)?;
        }
        match fs::rename(stage.join(staged_name), &current) {
            Ok(()) => replaced.push((current, saved)),
            Err(error) => {
                for (placed, old) in replaced.into_iter().rev() {
                    if placed.exists() {
                        fs::remove_dir_all(&placed).ok();
                    }
                    if old.exists() {
                        fs::rename(old, placed).ok();
                    }
                }
                if saved.exists() {
                    fs::rename(saved, current).ok();
                }
                return Err(error.into());
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn word(value: u32) -> [u8; 4] {
        value.to_le_bytes()
    }

    #[test]
    fn finds_psyq_text_cluster() {
        let mut payload = b"OVERLAY.DAT\0\0\0\0\0".to_vec();
        payload.extend([0; 16]);
        for value in [
            JR_RA,
            0x1021,
            JR_RA,
            0x1021,
            0x27BD_FFE8,
            0xAFBF_0010,
            JR_RA,
            0x27BD_0018,
            0x27BD_FFD0,
            0xAFBF_0028,
            JR_RA,
            0x27BD_0030,
        ] {
            payload.extend(word(value));
        }
        payload.extend(b"hello world\0\0\0\0");
        let (start, end) = find_text_range(&payload).unwrap();
        assert_eq!(start, 32);
        assert_eq!(end, 80);
    }

    #[test]
    fn patches_labels_and_function_references_per_binary() {
        let temp = tempfile::tempdir().unwrap();
        let binary = temp.path().join("asm/game");
        fs::create_dir_all(&binary).unwrap();
        fs::write(
            binary.join("function.s"),
            "glabel func_80001234\n/* 0 80001234 00000000 */ nop\n/* 4 80001238 00000000 */ beqz $v0, .L80001240\n/* C 80001240 00000000 */ nop\n",
        )
        .unwrap();
        fs::write(binary.join("rodata.s"), ".word D_80001234\n").unwrap();

        fix_asm_tree(&temp.path().join("asm")).unwrap();

        let function = fs::read_to_string(binary.join("function.s")).unwrap();
        assert!(function.contains(".L80001240:\n/* C 80001240"));
        assert_eq!(
            fs::read_to_string(binary.join("rodata.s")).unwrap(),
            ".word func_80001234\n"
        );
    }
}
