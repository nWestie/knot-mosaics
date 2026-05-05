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
    #[arg(long)]
    resume: bool,

    #[command[flatten]]
    filters: Filters,
}

fn main() -> Result<()> {
    // let args = CliArgs {
    //     mosaic_size: 3,
    //     mosaic_type: MosaicVariant::Mobius,
    //     max_lines: 100_000,
    //     base_dir: PathBuf::from("../data"),
    //     filters: Filters {
    //         discard_crossings_below: 0,
    //         remove_loops: true,
    //     },
    //     resume: false,
    // };
    let args = CliArgs::parse();
    dbg!(&args);
    let size: usize = args.mosaic_size;
    let folder_name = format!("{size}_{}", args.mosaic_type.dir_code());
    let output_folder = args.base_dir.join(folder_name);

    println!("generating ...");

    create_dir_all(&output_folder)?;
    let mosaic = Mosaic::new(size, args.mosaic_type);
    let generator = if args.resume {
        let g = Generator::resume_mosaic_gen(mosaic, &output_folder, args.max_lines)?;
        println!(
            "Resuming: {} complete",
            format_num!(".2%", g.calc_progress())
        );
        g
    } else {
        let outbuf = RollingBufWriter::new(&output_folder, args.max_lines, mosaic.get_len())?;
        Generator::new(outbuf, mosaic)
    };
    generate(generator, args.filters)?;

    let path = output_folder.join("COMPLETED");
    std::fs::File::create(path)?;
    Ok(())
}

struct Generator {
    branches: Vec<Vec<u8>>,
    depth: usize,
    mosaic: Mosaic,
    out_buff: RollingBufWriter,
    progress: Vec<(i32, i32)>, // (i,n) for each level, stores current index and total count of options
    start_ct: u64,
    gen_ct: u64,
}
impl Generator {
    fn new(out_buff: RollingBufWriter, mosaic: Mosaic) -> Generator {
        let len = mosaic.get_len();
        let mut branches: Vec<Vec<u8>> = vec![vec![]; len];
        let mut progress = vec![(0, 1i32); len];

        branches[0] = Vec::from(mosaic.get_valid_tiles(0));
        branches[0].reverse(); // this preserves increasing numeric order of the output
        progress[0] = (-1, branches[0].len() as i32);
        Generator {
            branches,
            depth: 0,
            mosaic,
            out_buff,
            progress,
            start_ct: 0,
            gen_ct: 0,
        }
    }
    /// `mosaic` should be an empty mosaic of the correct type.
    fn resume_mosaic_gen(
        mut mosaic: Mosaic,
        output_folder: &PathBuf,
        lines_per_file: usize,
    ) -> Result<Generator> {
        // getting all existing files
        let names = std::fs::read_dir(output_folder)?
            .filter_map(|p| p.ok())
            .filter_map(|p| p.file_name().into_string().ok());
        let mut last_ind = 0;

        // find the index of the last generated file
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

        // get the mosaic string that starts that file
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

        // rebuild mosaic generation object from string
        let mut branches: Vec<Vec<u8>> = vec![vec![]; mosaic.get_len()];
        let mut progress: Vec<(i32, i32)> = vec![(0, 1); mosaic.get_len()];

        for (i, ch) in mos_str.chars().enumerate() {
            let possible_vals = mosaic.get_valid_tiles(i);

            let num = ch.to_digit(16).map(|n| n as u8).ok_or_else(|| {
                Error::new(ErrorKind::InvalidData, "Mosaic has non-neumeric chars")
            })?;
            // Check that this tile is valid in this position
            if num != 12 {
                let Some(index) = possible_vals.iter().position(|val| *val == num) else {
                    return Err(Error::new(
                        ErrorKind::InvalidData,
                        format!("tile {num} at index {i} forms invalid mosaic"),
                    ));
                };
                // saving progress: "at this level I am on branch i of n"
                progress[i] = (index as i32, possible_vals.len() as i32);
                branches[i] = possible_vals[index + 1..].to_vec();
                branches[i].reverse();
                mosaic.set_tile(i, num);
            }
        }

        let mut out_buff = RollingBufWriter::resume_from(
            &output_folder,
            lines_per_file,
            mosaic.get_len(),
            last_ind,
        )?;
        out_buff.write_line(&mosaic.to_string())?;
        out_buff.flush()?;
        Ok(Generator {
            branches,
            depth: mosaic.get_len() - 1,
            mosaic,
            out_buff,
            progress,
            start_ct: (last_ind * 100_000) as u64,
            gen_ct: 0,
        })
    }
    fn calc_progress(&self) -> f64 {
        let mut denom: f64 = 1.;
        let mut sum: f64 = 0.;
        // the first 15 levels are probably a good enough guess
        for (i, n) in self.progress.iter().take(15) {
            denom *= *n as f64;
            sum += (*i as f64) / denom;
        }
        sum
    }
}

fn generate(mut g: Generator, filters: Filters) -> Result<()> {
    // let mut mosaic_ct: usize = 0;
    let t_start = Instant::now(); //Timing 

    'outer: loop {
        // moving to the next branch at <depth>
        if let Some(first) = g.branches[g.depth].pop() {
            g.mosaic.set_tile(g.depth, first);
            g.progress[g.depth].0 += 1; // stepping over to next 'branch'
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
            g.progress[g.depth] = (0, 1);
            g.depth -= 1;
            continue;
        }
        // descend down into the tree, finding branches (left side)
        while g.depth < g.mosaic.get_len() {
            g.branches[g.depth] = Vec::from(g.mosaic.get_valid_tiles(g.depth));
            g.branches[g.depth].reverse();
            if let Some(item) = g.branches[g.depth].pop() {
                g.mosaic.set_tile(g.depth, item);
                g.progress[g.depth] = (0, g.branches[g.depth].len() as i32 + 1);
                if g.mosaic.is_trivial(&filters) {
                    // this moves to the next branch at this depth.
                    continue 'outer;
                }
                g.depth += 1
            } else {
                // there are no valid tiles for this position, back out
                g.mosaic.set_tile(g.depth, 11);
                g.progress[g.depth] = (0, 1);
                g.depth -= 1;
                continue 'outer;
            }
        }

        g.depth -= 1;
        loop {
            let res = g.out_buff.write_line(&g.mosaic.to_string())?;
            g.gen_ct += 1;
            if let RollOver::Rolled(index) = res {
                let progress = g.calc_progress();
                let est_t_remains = estimate_time_remaining(g.gen_ct, g.start_ct, t_start, progress);
                println!(
                    "{}: on pt{index} - {} generated, {}\n - Est {}:{}:{} remaining",
                    g.mosaic.description_str(),
                    format_num!(",.3s", g.gen_ct as f64),
                    format_num!(".2%", progress),
                    est_t_remains / 3600,
                    (est_t_remains % 3600) / 60,
                    est_t_remains % 60,
                );
            }
            if let Some(item) = g.branches[g.depth].pop() {
                g.mosaic.set_tile(g.depth, item);
            } else {
                break;
            }
        }
        // clean up specifically the last tile
        g.mosaic.set_tile(g.depth, 11);
        g.progress[g.depth] = (0, 1);
        // the weird max here is to handle the case of a 1x1 mosaic
        g.depth = std::cmp::max(1, g.depth) - 1;
    }
    g.out_buff.flush()?;
    println!("Done - {} mosaics generated", g.gen_ct);
    println!("- Completed in {:.6} s)", t_start.elapsed().as_secs_f64(),);
    Ok(())
}

fn estimate_time_remaining(gen_ct: u64, base_ct: u64, t_start: Instant, progress: f64) -> u64 {
    let tot_gen = (gen_ct + base_ct) as f64;
    let est_total = tot_gen / progress;
    let est_remain = est_total - tot_gen;
    let elapsed = t_start.elapsed().as_secs_f64();
    let rate = (gen_ct as f64) / elapsed;
    (est_remain / rate) as u64
}
