use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use psxdecomp::manifest::Manifest;
use psxdecomp::plan::Plan;

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error:#}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        print_help();
        return Ok(());
    };
    if command == "--version" || command == "version" {
        println!("psxdecomp {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    if command == "--help" || command == "help" {
        print_help();
        return Ok(());
    }
    let options = Options::parse(args.collect())?;
    let root = options
        .path_or("root", ".")?
        .canonicalize()
        .context("resolve project root")?;
    let manifest_path = options.path_or("manifest", "psxdecomp.toml")?;
    let manifest = Manifest::load(&root, &manifest_path)?;

    match command.as_str() {
        "validate" => {
            println!(
                "{}: {} binaries",
                manifest.project.name,
                manifest.binary.len()
            );
        }
        "plan" => {
            print!("{}", Plan::discover(&root, &manifest)?.write_tsv());
        }
        "compile" => {
            psxdecomp::asm::compile(
                &root,
                &manifest,
                &options.required_path("source")?,
                &options.required_path("expected-asm")?,
                &options.required_path("output")?,
            )?;
        }
        "assemble" => {
            psxdecomp::asm::assemble(
                &root,
                &manifest,
                &options.required_path("source")?,
                &options.required_path("output")?,
                options.required("export-locals")? == "true",
            )?;
        }
        "select" => {
            psxdecomp::asm::select(
                &root,
                options.required("symbol")?,
                &options.required_path("expected")?,
                &options.required_path("fallback")?,
                &options.required_path("candidate")?,
                &options.required_path("output")?,
            )?;
        }
        "link" => {
            let plan = read_plan(&options.required_path("plan")?)?;
            psxdecomp::asm::link(
                &root,
                &manifest,
                &plan,
                &options.required_path("build-dir")?,
                options.required("binary")?,
                &options.required_path("elf")?,
                &options.required_path("output")?,
            )?;
        }
        "verify" => {
            psxdecomp::asm::verify(
                &manifest,
                options.required("binary")?,
                &options.required_path("input")?,
                &options.required_path("stamp")?,
            )?;
        }
        "progress" => {
            let plan = read_plan(&options.required_path("plan")?)?;
            psxdecomp::report::generate(
                &manifest,
                &plan,
                &options.required_path("build-dir")?,
                &options.required_path("output")?,
            )?;
        }
        "regenerate" => psxdecomp::regenerate::run(&root, &manifest)?,
        other => bail!("unknown command {other}"),
    }
    Ok(())
}

fn read_plan(path: &Path) -> Result<Plan> {
    Plan::read_tsv(&fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?)
}

#[derive(Debug)]
struct Options {
    values: BTreeMap<String, String>,
}

impl Options {
    fn parse(args: Vec<String>) -> Result<Self> {
        let mut values = BTreeMap::new();
        let mut i = 0;
        while i < args.len() {
            let key = args[i]
                .strip_prefix("--")
                .with_context(|| format!("unexpected argument {}", args[i]))?;
            let value = args
                .get(i + 1)
                .with_context(|| format!("--{key} requires a value"))?;
            if value.starts_with("--") {
                bail!("--{key} requires a value");
            }
            if values.insert(key.to_owned(), value.to_owned()).is_some() {
                bail!("duplicate --{key}");
            }
            i += 2;
        }
        Ok(Self { values })
    }

    fn required(&self, key: &str) -> Result<&str> {
        self.values
            .get(key)
            .map(String::as_str)
            .with_context(|| format!("missing --{key}"))
    }

    fn required_path(&self, key: &str) -> Result<PathBuf> {
        Ok(self.required(key)?.into())
    }

    fn path_or(&self, key: &str, default: &str) -> Result<PathBuf> {
        Ok(self
            .values
            .get(key)
            .map(PathBuf::from)
            .unwrap_or_else(|| default.into()))
    }
}

fn print_help() {
    println!(
        "psxdecomp <validate|plan|compile|assemble|select|link|verify|progress|regenerate> [options]"
    );
}
