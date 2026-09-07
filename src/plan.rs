use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use regex::Regex;

use crate::manifest::Manifest;

pub fn listing_wrapper_reason(source: &Path) -> Result<Option<String>> {
    let text = fs::read_to_string(source)?;
    let comment = Regex::new(r"(?s)/\*.*?\*/|//[^\n]*")?;
    let stripped = comment.replace_all(&text, "");
    let asm = Regex::new(r"\b__asm(?:__)?\b|\basm\s*(?:(?:__)?volatile(?:__)?\s*)?\(")?;
    Ok(asm.is_match(&stripped).then(|| {
        format!(
            "listing wrapper: {} uses inline assembly; matching sources must be C",
            source.display()
        )
    }))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Function {
    pub binary: String,
    pub symbol: String,
    pub asm: PathBuf,
    pub source: Option<PathBuf>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Assembly {
    pub binary: String,
    pub source: PathBuf,
    pub role: AssemblyRole,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AssemblyRole {
    Header,
    Data,
}

#[derive(Debug, Clone, Default)]
pub struct Plan {
    pub binaries: Vec<String>,
    pub functions: Vec<Function>,
    pub assembly: Vec<Assembly>,
}

pub fn normalize_symbol(name: &str) -> String {
    let stem = Path::new(name)
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy();
    let stem = stem
        .strip_prefix("func_")
        .or_else(|| stem.strip_prefix("fun_"))
        .or_else(|| stem.strip_prefix("FUNC_"))
        .or_else(|| stem.strip_prefix("FUN_"))
        .unwrap_or(&stem);
    stem.replace('_', "").to_ascii_uppercase()
}

impl Plan {
    pub fn discover(root: &Path, manifest: &Manifest) -> Result<Self> {
        let include_asm =
            Regex::new(r#"INCLUDE_ASM\(\s*"([^"]+)"\s*,\s*([A-Za-z0-9_.$]+)\s*\)\s*;"#)?;
        let include_c = Regex::new(r#"^\s*#include\s+"([^"]+\.c)"\s*$"#)?;
        let empty_function = Regex::new(r"^\s*void\s+([A-Za-z0-9_.$]+)\s*\(void\)\s*\{\s*$")?;
        let mut plan = Self::default();

        for binary in &manifest.binary {
            plan.binaries.push(binary.id.clone());
            let tu_path = root
                .join("src")
                .join(&binary.id)
                .join(format!("{}.c", binary.tu));
            let text = fs::read_to_string(&tu_path)
                .with_context(|| format!("read translation unit {}", tu_path.display()))?;
            let expected_dir = root
                .join("asm")
                .join(&binary.id)
                .join("nonmatchings")
                .join(&binary.tu);

            let lines: Vec<_> = text.lines().collect();
            for (index, line) in lines.iter().enumerate() {
                if let Some(caps) = include_asm.captures(line) {
                    let folder = PathBuf::from(&caps[1]);
                    let symbol = caps[2].to_owned();
                    let asm = folder.join(format!("{symbol}.s"));
                    if !root.join(&asm).is_file() {
                        bail!("{} references missing {}", tu_path.display(), asm.display());
                    }
                    plan.functions.push(Function {
                        binary: binary.id.clone(),
                        symbol,
                        asm,
                        source: None,
                    });
                    continue;
                }
                if let Some(caps) = empty_function.captures(line)
                    && lines.get(index + 1).is_some_and(|line| line.trim() == "}")
                {
                    let symbol = caps[1].to_owned();
                    let asm_abs = find_expected_asm(&expected_dir, &symbol)?;
                    let asm = asm_abs.strip_prefix(root).unwrap_or(&asm_abs).to_owned();
                    plan.functions.push(Function {
                        binary: binary.id.clone(),
                        symbol,
                        asm,
                        source: None,
                    });
                    continue;
                }
                let Some(caps) = include_c.captures(line) else {
                    continue;
                };
                let source = PathBuf::from("src").join(&binary.id).join(&caps[1]);
                let source_abs = root.join(&source);
                if !source_abs.is_file() {
                    bail!(
                        "{} includes missing {}",
                        tu_path.display(),
                        source.display()
                    );
                }
                let requested = source.file_stem().unwrap_or_default().to_string_lossy();
                let asm_abs = find_expected_asm(&expected_dir, &requested)?;
                let asm = asm_abs.strip_prefix(root).unwrap_or(&asm_abs).to_owned();
                let symbol = asm
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .into_owned();
                let source = listing_wrapper_reason(&source_abs)?
                    .is_none()
                    .then_some(source);
                plan.functions.push(Function {
                    binary: binary.id.clone(),
                    symbol,
                    asm,
                    source,
                });
            }

            let asm_root = root.join("asm").join(&binary.id);
            for entry in walkdir::WalkDir::new(&asm_root).sort_by_file_name() {
                let entry = entry?;
                if !entry.file_type().is_file() || entry.path().extension().is_none_or(|x| x != "s")
                {
                    continue;
                }
                let rel = entry.path().strip_prefix(root)?.to_owned();
                let components: Vec<_> = rel.components().collect();
                if components
                    .iter()
                    .any(|c| c.as_os_str() == "nonmatchings" || c.as_os_str() == "matchings")
                {
                    continue;
                }
                let role = if entry.file_name() == "header.s" {
                    AssemblyRole::Header
                } else {
                    AssemblyRole::Data
                };
                plan.assembly.push(Assembly {
                    binary: binary.id.clone(),
                    source: rel,
                    role,
                });
            }
        }
        Ok(plan)
    }

    pub fn write_tsv(&self) -> String {
        let mut out = String::new();
        for binary in &self.binaries {
            out.push_str("binary\t");
            out.push_str(binary);
            out.push('\n');
            for f in self.functions.iter().filter(|f| &f.binary == binary) {
                out.push_str("function\t");
                out.push_str(&f.binary);
                out.push('\t');
                out.push_str(&f.symbol);
                out.push('\t');
                out.push_str(&f.asm.to_string_lossy());
                out.push('\t');
                out.push_str(
                    &f.source
                        .as_ref()
                        .map(|p| p.to_string_lossy())
                        .unwrap_or_else(|| "-".into()),
                );
                out.push('\n');
            }
            for a in self.assembly.iter().filter(|a| &a.binary == binary) {
                out.push_str(match a.role {
                    AssemblyRole::Header => "header",
                    AssemblyRole::Data => "data",
                });
                out.push('\t');
                out.push_str(&a.binary);
                out.push('\t');
                out.push_str(&a.source.to_string_lossy());
                out.push('\n');
            }
            out.push_str("binary_end\t");
            out.push_str(binary);
            out.push('\n');
        }
        out
    }

    pub fn read_tsv(text: &str) -> Result<Self> {
        let mut plan = Self::default();
        for (line_no, line) in text.lines().enumerate() {
            if line.is_empty() {
                continue;
            }
            let fields: Vec<_> = line.split('\t').collect();
            match fields.as_slice() {
                ["binary", binary] => plan.binaries.push((*binary).into()),
                ["binary_end", _] => {}
                ["function", binary, symbol, asm, source] => plan.functions.push(Function {
                    binary: (*binary).into(),
                    symbol: (*symbol).into(),
                    asm: (*asm).into(),
                    source: (*source != "-").then(|| PathBuf::from(source)),
                }),
                [kind @ ("header" | "data"), binary, source] => plan.assembly.push(Assembly {
                    binary: (*binary).into(),
                    source: (*source).into(),
                    role: if *kind == "header" {
                        AssemblyRole::Header
                    } else {
                        AssemblyRole::Data
                    },
                }),
                _ => bail!("invalid plan line {}: {}", line_no + 1, line),
            }
        }
        Ok(plan)
    }
}

fn find_expected_asm(dir: &Path, requested: &str) -> Result<PathBuf> {
    let exact = dir.join(format!("{requested}.s"));
    if exact.is_file() {
        return Ok(exact);
    }
    let key = normalize_symbol(requested);
    for entry in fs::read_dir(dir).with_context(|| format!("read {}", dir.display()))? {
        let path = entry?.path();
        if path.extension().is_some_and(|x| x == "s")
            && normalize_symbol(
                path.file_stem()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .as_ref(),
            ) == key
        {
            return Ok(path);
        }
    }
    bail!(
        "no expected assembly for {requested} under {}",
        dir.display()
    )
}

pub fn safe_name(value: &str) -> String {
    value
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect()
}

pub fn expected_object(binary: &str, symbol: &str) -> String {
    format!("expected__{}__{}.o", safe_name(binary), safe_name(symbol))
}

pub fn candidate_object(binary: &str, symbol: &str) -> String {
    format!("candidate__{}__{}.o", safe_name(binary), safe_name(symbol))
}

pub fn selected_object(binary: &str, symbol: &str) -> String {
    format!("selected__{}__{}.o", safe_name(binary), safe_name(symbol))
}

pub fn link_object(binary: &str, symbol: &str) -> String {
    format!("link__{}__{}.o", safe_name(binary), safe_name(symbol))
}

pub fn assembly_object(binary: &str, source: &Path) -> String {
    format!(
        "assembly__{}__{}.o",
        safe_name(binary),
        safe_name(source.to_string_lossy().as_ref())
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_legacy_function_names() {
        assert_eq!(normalize_symbol("func_8001a968.c"), "8001A968");
        assert_eq!(normalize_symbol("FUN_8001_A968"), "8001A968");
    }

    #[test]
    fn plan_tsv_round_trips() {
        let plan = Plan {
            binaries: vec!["main".into()],
            functions: vec![Function {
                binary: "main".into(),
                symbol: "func_1".into(),
                asm: "asm/main/func_1.s".into(),
                source: Some("src/main/func_1.c".into()),
            }],
            assembly: vec![Assembly {
                binary: "main".into(),
                source: "asm/main/header.s".into(),
                role: AssemblyRole::Header,
            }],
        };
        assert_eq!(
            Plan::read_tsv(&plan.write_tsv()).unwrap().functions,
            plan.functions
        );
    }
}
