use std::fs;
use std::path::Path;

use anyhow::{Context, Result, bail};
use serde_json::json;

use crate::manifest::Manifest;
use crate::plan::{AssemblyRole, Plan, assembly_object, candidate_object, expected_object};
use crate::process;

pub fn generate(manifest: &Manifest, plan: &Plan, build_dir: &Path, output: &Path) -> Result<()> {
    let mut units = Vec::new();
    for function in &plan.functions {
        let target = expected_object(&function.binary, &function.symbol);
        let source = function.source.as_ref().unwrap_or(&function.asm);
        let mut unit = json!({
            "name": format!("{}/{}", function.binary, function.symbol),
            "target_path": target,
            "metadata": {
                "progress_categories": [function.binary],
                "source_path": build_relative(build_dir, source),
            }
        });
        if function.source.is_some() {
            let base = candidate_object(&function.binary, &function.symbol);
            if !build_dir.join(&base).is_file() {
                bail!(
                    "missing candidate object {}",
                    build_dir.join(&base).display()
                );
            }
            unit["base_path"] = json!(base);
        }
        units.push(unit);
    }
    for assembly in plan
        .assembly
        .iter()
        .filter(|a| a.role == AssemblyRole::Data)
    {
        let object = assembly_object(&assembly.binary, &assembly.source);
        units.push(json!({
            "name": format!("{}/{}", assembly.binary, assembly.source.file_stem().unwrap_or_default().to_string_lossy()),
            "target_path": object,
            "metadata": {
                "progress_categories": [assembly.binary],
                "source_path": build_relative(build_dir, &assembly.source),
            }
        }));
    }
    let categories: Vec<_> = manifest
        .binary
        .iter()
        .map(|b| json!({"id": b.id, "name": b.name}))
        .collect();
    let config = json!({
        "$schema": "https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json",
        "custom_make": "meson",
        "custom_args": ["compile", "-C", "."],
        "build_target": true,
        "build_base": true,
        "progress_categories": categories,
        "units": units,
    });
    fs::create_dir_all(build_dir)?;
    fs::write(
        build_dir.join("objdiff.json"),
        serde_json::to_string_pretty(&config)? + "\n",
    )?;
    process::run(
        "objdiff-cli",
        &[
            "report".into(),
            "generate".into(),
            "-p".into(),
            build_dir.as_os_str().into(),
            "-o".into(),
            output.as_os_str().into(),
            "-f".into(),
            "json".into(),
            "-c".into(),
            "function_reloc_diffs=none".into(),
        ],
        build_dir,
    )?;
    let text = fs::read_to_string(output).with_context(|| format!("read {}", output.display()))?;
    if text.contains("/Users/") || text.contains("/home/") {
        fs::remove_file(output).ok();
        bail!("refusing report containing a local path");
    }
    println!("wrote {}", output.display());
    Ok(())
}

fn build_relative(build_dir: &Path, source: &Path) -> String {
    let depth = build_dir.components().count();
    let mut path = std::path::PathBuf::new();
    for _ in 0..depth.min(1) {
        path.push("..");
    }
    path.push(source);
    path.to_string_lossy().replace('\\', "/")
}
