mod conn_table;
mod mosaics;
mod rolling_buff;

use clap::Parser;
use format_num::format_num;
use std::fs::create_dir_all;
use std::io::Result;
use std::path::PathBuf;
use std::time::Instant;

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

    #[command[flatten]]
    filters: Filters,
}

fn main() -> Result<()> {
    // let args = CliArgs {
    //     mosaic_size: 1,
    //     mosaic_type: MosaicVariant::Cubic { cubic_type: String::from("6") },
    //     max_lines: 100_000,
    //     base_dir: PathBuf::from("../data"),
    //     discard_crossings_below: 0,
    //     remove_loops: false,
    // };
    let args = CliArgs::parse();
    dbg!(&args);
    let size: usize = args.mosaic_size;
    let folder_name = format!("{size}_{}", args.mosaic_type.dir_code());
    let output_folder = args.base_dir.join(folder_name);

    let now = Instant::now(); //Timing 
    println!("generating ...");

    create_dir_all(&output_folder)?;
    let mosaic = Mosaic::new(size, args.mosaic_type);
    let mut outbuf = RollingBufWriter::new(&output_folder, args.max_lines, mosaic.get_len())?;
    mosaic_gen(&mut outbuf, mosaic, args.filters)?;
    outbuf.flush()?;

    let path = output_folder.join("COMPLETED");
    std::fs::File::create(path)?;
    println!("- Completed in {:.6} s)", now.elapsed().as_secs_f64(),);
    Ok(())
}

fn mosaic_gen(out_buff: &mut RollingBufWriter, mut mosaic: Mosaic, filters: Filters) -> Result<()> {
    let mut branches: Vec<Vec<u8>> = vec![vec![]; mosaic.get_len()];
    let mut mosaic_ct = 0;
    let mut depth = 0;
    branches[0] = Vec::from(mosaic.get_valid_tiles(0));
    branches[0].reverse(); // this preserves increasing numeric order of the output
    'outer: loop {
        // moving to the next branch at <depth>
        if let Some(first) = branches[depth].pop() {
            mosaic.set_tile(depth, first);
            // this does not hit at all for cubic?? Likely because the only metric is
            if mosaic.is_trivial(&filters) {
                continue; // this will go to next branch at same depth
            }
            depth += 1;
        } else {
            // if all branches explored, back out a level
            if depth == 0 {
                break; // exit if we explore all top-level branches
            }
            mosaic.set_tile(depth, 11);
            depth -= 1;
            continue;
        }
        // descend down into the tree, finding branches (left side)
        while depth < mosaic.get_len() {
            branches[depth] = Vec::from(mosaic.get_valid_tiles(depth));
            branches[depth].reverse();
            if let Some(item) = branches[depth].pop() {
                mosaic.set_tile(depth, item);
                // TODO: Possibly skipping logic here too?
                if mosaic.is_trivial(&filters) {
                    // this moves to the next branch at this depth.
                    continue 'outer;
                }
                depth += 1
            } else {
                mosaic.set_tile(depth, 11);
                depth -= 1;
                continue 'outer;
            }
        }

        depth -= 1;
        loop {
            let res = out_buff.write_line(&mosaic.to_string())?;
            mosaic_ct += 1;
            if let RollOver::Rolled(index) = res {
                println!(
                    "{}: on pt{index} - {} generated",
                    mosaic.description_str(),
                    format_num!(",.3s", mosaic_ct as f64),
                );
            }
            if let Some(item) = branches[depth].pop() {
                mosaic.set_tile(depth, item);
            } else {
                break;
            }
        }
        mosaic.set_tile(depth, 11);
        // the weird max here is to handle the case of a 1x1 mosaic
        depth = std::cmp::max(1, depth) - 1;
    }
    println!("Done - {mosaic_ct} mosaics generated");
    Ok(())
}
