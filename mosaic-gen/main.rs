mod conn_table;
mod mosaics;
mod rolling_buff;
use std::fs::File;
use std::io::{Error, ErrorKind};

use clap::Parser;
use format_num::format_num;
use std::io::{BufRead, Result};
use std::path::PathBuf;
use std::time::Instant;
use std::{fs::create_dir_all, io::BufReader};

use crate::{conn_table::CUBIC_TYPES, mosaics::Mosaic};
use rolling_buff::{RollOver, RollingBufWriter};

#[derive(PartialEq, clap::Subcommand, Debug)]
enum MosaicVariant {
    /// Mosaic with no edge connections
    Flat,
    /// Mosaic with Left and Right edges stiched
    Cylindrical,
    /// Mosaic with Left and Right edges stiched
    Toric,
    /// Mosaic with L/R edges stiched, but twisted (top-left -> bottom right)
    Mobius,
    Cubic {
        #[arg(value_parser = clap::builder::PossibleValuesParser::new(CUBIC_TYPES.iter().map(|c|c.name)),)]
        cubic_type: String,
    },
}
impl MosaicVariant {
    fn dir_code(&self) -> String {
        match self {
            MosaicVariant::Flat => String::from("flat"),
            MosaicVariant::Cylindrical => String::from("cyl"),
            MosaicVariant::Toric => String::from("toric"),
            MosaicVariant::Mobius => String::from("mobius"),
            MosaicVariant::Cubic { cubic_type } => {
                format!("cubic/{cubic_type}")
            }
        }
    }
}
impl std::fmt::Display for MosaicVariant {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.dir_code())
    }
}
#[derive(clap::Args, Debug)]
struct Filters {
    // mosaics with < this number of crossings will not be saved
    // set to zero to include all mosaics
    /// discard knots with less than N crossings
    #[arg(short, long, default_value_t = 3)]
    discard_crossings_below: usize,
    /// discard mosaics that contain trivial loops
    #[arg(short, long)]
    remove_loops: bool,
}

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct CliArgs {
    /// Number of times to greet
    mosaic_size: usize,
    /// Name of the person to greet
    #[command(subcommand)]
    mosaic_type: MosaicVariant,
    /// Max lines in each output file
    #[arg(short, long, default_value_t = 100_000)]
    max_lines: usize,
    /// Folder to put output
    #[arg(short, long, default_value_os_t =PathBuf::from("../data/"))]
    base_dir: PathBuf,
    /// Resume generation of partially complete results
    #[arg(short, long)]
    resume: bool,

    #[command[flatten]]
    filters: Filters,
}

fn main() -> Result<()> {
    let args = CliArgs {
        mosaic_size: 4,
        mosaic_type: MosaicVariant::Cubic {
            cubic_type: String::from("2"),
        },
        max_lines: 100_000,
        base_dir: PathBuf::from("../data"),
        filters: Filters {
            discard_crossings_below: 3,
            remove_loops: true,
        },
        resume: true,
    };
    // let args = CliArgs::parse();
    dbg!(&args);
    let size: usize = args.mosaic_size;
    let folder_name = format!("{size}_{}", args.mosaic_type.dir_code());
    let output_folder = args.base_dir.join(folder_name);

    let t_start = Instant::now(); //Timing 
    println!("generating ...");

    create_dir_all(&output_folder)?;
    let mosaic = Mosaic::new(size, args.mosaic_type);
    let generator = if args.resume {
        resume_mosaic_gen(mosaic, &output_folder, args.max_lines)?
    } else {
        let outbuf = RollingBufWriter::new(&output_folder, args.max_lines, mosaic.get_len())?;
        Generator::new(outbuf, mosaic)
    };
    mosaic_gen(generator, args.filters)?;

    let path = output_folder.join("COMPLETED");
    std::fs::File::create(path)?;
    println!("- Completed in {:.6} s)", t_start.elapsed().as_secs_f64(),);
    Ok(())
}

/// `mosaic` should be an empty mosaic of the correct type.
fn resume_mosaic_gen(
    mut mosaic: Mosaic,
    output_folder: &PathBuf,
    lines_per_file: usize,
) -> Result<Generator> {
    let names = std::fs::read_dir(output_folder)?
        .filter_map(|p| p.ok())
        .filter_map(|p| p.file_name().into_string().ok());
    let mut last_ind = 0;

    for n in names {
        if n == "COMPLETED" {
            return Err(Error::other("Generation Already Complete!"));
        }
        let Some(num) = n
            .strip_prefix("pt")
            .and_then(|s| s.strip_suffix(".txt"))
            .and_then(|s| s.parse::<usize>().ok())
        else {
            continue;
        };
        last_ind = std::cmp::max(num, last_ind);
    }
    let mut mos_str = String::new();
    let file = File::open(RollingBufWriter::path_from_index(output_folder, last_ind))?;
    BufReader::new(file).read_line(&mut mos_str)?;
    let mos_str = mos_str.trim();
    if !mos_str.is_ascii() {
        return Err(Error::new(
            ErrorKind::InvalidData,
            "Mosaic string is not ASCII",
        ));
    }
    let mut branches: Vec<Vec<u8>> = vec![vec![]; mosaic.get_len()];
    // build mosaic from string
    for (i, ch) in mos_str.chars().enumerate() {
        let possible_vals = mosaic.get_valid_tiles(i);

        let num = ch
            .to_digit(16)
            .map(|n| n as u8)
            .ok_or_else(|| Error::new(ErrorKind::InvalidData, "Mosaic has non-neumeric chars"))?;
        // Check that this tile is valid in this position
        if num != 12 {
            let Some(index) = possible_vals.iter().position(|val| *val == num) else {
                return Err(Error::new(
                    ErrorKind::InvalidData,
                    format!("tile {num} at index {i} forms invalid mosaic"),
                ));
            };
            branches[i] = possible_vals[index + 1..].to_vec();
            branches[i].reverse();
            mosaic.set_tile(i, num);
        }
    }

    let mut out_buff =
        RollingBufWriter::resume_from(&output_folder, lines_per_file, mosaic.get_len(), last_ind)?;
    out_buff.write_line(&mosaic.to_string())?;
    out_buff.flush()?;
    Ok(Generator {
        branches,
        depth: mosaic.get_len() - 1,
        mosaic,
        out_buff,
    })
}

struct Generator {
    branches: Vec<Vec<u8>>,
    depth: usize,
    mosaic: Mosaic,
    out_buff: RollingBufWriter,
}
impl Generator {
    fn new(out_buff: RollingBufWriter, mosaic: Mosaic) -> Generator {
        let mut branches: Vec<Vec<u8>> = vec![vec![]; mosaic.get_len()];

        branches[0] = Vec::from(mosaic.get_valid_tiles(0));
        branches[0].reverse(); // this preserves increasing numeric order of the output
        Generator {
            branches,
            depth: 0,
            mosaic,
            out_buff,
        }
    }
}

fn mosaic_gen(mut g: Generator, filters: Filters) -> Result<()> {
    let mut mosaic_ct: usize = 0;
    'outer: loop {
        // moving to the next branch at <depth>
        if let Some(first) = g.branches[g.depth].pop() {
            g.mosaic.set_tile(g.depth, first);
            // this does not hit at all for cubic?? Likely because the only metric is
            if g.mosaic.is_trivial(&filters) {
                continue; // this will go to next branch at same depth
            }
            g.depth += 1;
        } else {
            // if all branches explored, back out a level
            if g.depth == 0 {
                break; // exit if we explore all top-level branches
            }
            g.mosaic.set_tile(g.depth, 11);
            g.depth -= 1;
            continue;
        }
        // descend down into the tree, finding branches (left side)
        while g.depth < g.mosaic.get_len() {
            g.branches[g.depth] = Vec::from(g.mosaic.get_valid_tiles(g.depth));
            g.branches[g.depth].reverse();
            if let Some(item) = g.branches[g.depth].pop() {
                g.mosaic.set_tile(g.depth, item);
                if g.mosaic.is_trivial(&filters) {
                    // this moves to the next branch at this depth.
                    continue 'outer;
                }
                g.depth += 1
            } else {
                g.mosaic.set_tile(g.depth, 11);
                g.depth -= 1;
                continue 'outer;
            }
        }

        g.depth -= 1;
        loop {
            let res = g.out_buff.write_line(&g.mosaic.to_string())?;
            mosaic_ct += 1;
            if let RollOver::Rolled(index) = res {
                println!(
                    "{}: on pt{index} - {} generated",
                    g.mosaic.description_str(),
                    format_num!(",.3s", mosaic_ct as f64),
                );
            }
            if let Some(item) = g.branches[g.depth].pop() {
                g.mosaic.set_tile(g.depth, item);
            } else {
                break;
            }
        }
        g.mosaic.set_tile(g.depth, 11);
        // the weird max here is to handle the case of a 1x1 mosaic
        g.depth = std::cmp::max(1, g.depth) - 1;
    }
    g.out_buff.flush()?;
    println!("Done - {mosaic_ct} mosaics generated");
    Ok(())
}
