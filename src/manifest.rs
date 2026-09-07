use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub project: Project,
    #[serde(default)]
    pub toolchain: Toolchain,
    pub binary: Vec<Binary>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Project {
    pub name: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Toolchain {
    pub cpp: String,
    pub cc1: String,
    pub assembler: String,
    pub linker: String,
    pub objcopy: String,
    pub maspsx: String,
    pub aspsx_version: String,
    pub c_args: Vec<String>,
    pub assembler_args: Vec<String>,
    pub linker_args: Vec<String>,
}

impl Default for Toolchain {
    fn default() -> Self {
        Self {
            cpp: "cpp-2.8.1-psx".into(),
            cc1: "cc1-2.8.1-psx".into(),
            assembler: "mipsel-linux-gnu-as".into(),
            linker: "mipsel-linux-gnu-ld".into(),
            objcopy: "mipsel-linux-gnu-objcopy".into(),
            maspsx: "maspsx".into(),
            aspsx_version: "2.79".into(),
            c_args: vec!["-O2".into(), "-G0".into(), "-fno-schedule-insns".into()],
            assembler_args: vec![
                "-EL".into(),
                "-march=r4000".into(),
                "-no-pad-sections".into(),
            ],
            linker_args: vec!["-EL".into()],
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Binary {
    pub id: String,
    pub name: String,
    pub kind: BinaryKind,
    pub tu: String,
    pub sha1: String,
    pub size: u64,
    pub splat_config: PathBuf,
    pub linker_template: PathBuf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BinaryKind {
    Executable,
    Overlay,
}

impl Manifest {
    pub fn load(root: &Path, path: &Path) -> Result<Self> {
        let path = if path.is_absolute() {
            path.to_owned()
        } else {
            root.join(path)
        };
        let text = fs::read_to_string(&path)
            .with_context(|| format!("read manifest {}", path.display()))?;
        let manifest: Self =
            toml::from_str(&text).with_context(|| format!("parse manifest {}", path.display()))?;
        manifest.validate(root)?;
        Ok(manifest)
    }

    pub fn validate(&self, root: &Path) -> Result<()> {
        if self.project.name.trim().is_empty() {
            bail!("project.name must not be empty");
        }
        if self.binary.is_empty() {
            bail!("manifest must declare at least one [[binary]]");
        }
        let mut ids = std::collections::BTreeSet::new();
        for binary in &self.binary {
            if !ids.insert(&binary.id) {
                bail!("duplicate binary id {}", binary.id);
            }
            if !binary
                .id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_')
            {
                bail!(
                    "binary id {} must use only letters, digits, and underscores",
                    binary.id
                );
            }
            if binary.sha1.len() != 40 || !binary.sha1.bytes().all(|b| b.is_ascii_hexdigit()) {
                bail!("binary {} has invalid SHA-1", binary.id);
            }
            if binary.size == 0 {
                bail!("binary {} has zero size", binary.id);
            }
            for (label, path) in [
                ("splat_config", &binary.splat_config),
                ("linker_template", &binary.linker_template),
            ] {
                if path.is_absolute()
                    || path
                        .components()
                        .any(|c| c == std::path::Component::ParentDir)
                {
                    bail!(
                        "binary {} {} must be a project-relative path",
                        binary.id,
                        label
                    );
                }
                if !root.join(path).is_file() {
                    bail!(
                        "binary {} {} does not exist: {}",
                        binary.id,
                        label,
                        path.display()
                    );
                }
            }
            let tu = root
                .join("src")
                .join(&binary.id)
                .join(format!("{}.c", binary.tu));
            if !tu.is_file() {
                bail!(
                    "binary {} translation unit does not exist: {}",
                    binary.id,
                    tu.display()
                );
            }
        }
        Ok(())
    }

    pub fn binary(&self, id: &str) -> Result<&Binary> {
        self.binary
            .iter()
            .find(|b| b.id == id)
            .with_context(|| format!("unknown binary {id}"))
    }
}
