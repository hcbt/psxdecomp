use std::ffi::OsString;
use std::path::Path;
use std::process::{Command, Stdio};

use anyhow::{Context, Result, bail};

pub fn run(program: &str, args: &[OsString], cwd: &Path) -> Result<()> {
    let status = Command::new(program)
        .args(args)
        .current_dir(cwd)
        .stdin(Stdio::null())
        .status()
        .with_context(|| format!("run {program}"))?;
    if !status.success() {
        bail!("{program} failed with {status}");
    }
    Ok(())
}

pub fn capture(program: &str, args: &[OsString], cwd: &Path) -> Result<Vec<u8>> {
    let output = Command::new(program)
        .args(args)
        .current_dir(cwd)
        .stdin(Stdio::null())
        .output()
        .with_context(|| format!("run {program}"))?;
    if !output.status.success() {
        bail!(
            "{} failed with {}:\n{}",
            program,
            output.status,
            String::from_utf8_lossy(&output.stderr)
        );
    }
    Ok(output.stdout)
}
