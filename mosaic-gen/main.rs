mod conn_table;
mod mosaics;
mod rolling_buff;

use clap::Parser;
use format_num::format_num;
use std::io::Result;
use std::path::PathBuf;
use std::time::Instant;
use std::fs::create_dir_all;

use crate::mosaics::Mosaic;
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
        cubic_type: u8,
    },
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
    #[arg(short, long, default_value_t = 50_000)]
    max_lines: usize,
    /// Folder to put output
    #[arg(short, long, default_value_os_t =PathBuf::from("../data/"))]
    base_dir: PathBuf,
    /// discard knots with less than N crossings
    #[arg(short, long, default_value_t = 0)]
    discard_crossings_below: usize,
    /// discard knots with less than N crossings
    #[arg(short, long)]
    remove_loops: bool,
}

fn main() -> Result<()> {
    let args = CliArgs::parse();
    // mosaics with <= this number of crossings will not be saved
    // for 5 crossings, we don't need anything <= 5
    // for 4 crossings, anything <=2
    // set to zero to include all mosaics
    let size: usize = args.mosaic_size;
    let output_folder = "../data/1_toric";

    // let max_lines = 50_000;
    create_dir_all(output_folder)?;
    let mut outbuf = RollingBufWriter::new(output_folder, args.max_lines)?;

    let now = Instant::now(); //Timing 

    println!("generating ...");
    mosaic_gen(&mut outbuf, size, MosaicVariant::Toric)?;
    print!(
        "Generation complete! ({:.6} s)",
        now.elapsed().as_secs_f64()
    );
    outbuf.flush()?;
    Ok(())
}

fn mosaic_gen(out_buff: &mut RollingBufWriter, size: usize, var: MosaicVariant) -> Result<()> {
    let mut mosaic = Mosaic::new(size, var);
    let mut branches: Vec<Vec<u8>> = vec![vec![]; mosaic.get_len()];
    let mut mosaic_ct = 0;
    let mut depth = 0;
    branches[0] = Vec::from(mosaic.get_valid_tiles(0));
    branches[0].reverse(); // this preserves increasing numeric order of the output
    'outer: loop {
        // moving to the next branch at <depth>
        if let Some(first) = branches[depth].pop() {
            mosaic.set_tile(depth, first);
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
                    "on pt{index} - {} generated, {} saved",
                    format_num!(",.3s", mosaic_ct as f64),
                    format_num!(",.3s", (out_buff.max_lines * index) as f64)
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
    Ok(())
}

