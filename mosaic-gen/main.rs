#![allow(unused)]
mod conn_table;
mod mosaics;
mod rolling_buff;

use format_num::format_num;
use std::io::Result;
use std::time::Instant;
use std::{default, fs::create_dir_all};

use crate::mosaics::Mosaic;
use rolling_buff::{RollOver, RollingBufWriter};

#[derive(PartialEq)]
enum MosaicVariant {
    Flat,
    Cylindrical,
    Toric,
    Cubic,
    Mobius,
}

#[derive(Clone, Copy, PartialEq)]
enum Conn {
    No = 0,
    Yes = 1,
    Maybe = 2,
}
#[derive(Clone, Copy)]
enum Side {
    Right = 0,
    Up = 1,
    Left = 2,
    Down = 3,
}
#[derive(Clone, Copy, PartialEq)]
struct ConnEntry {
    conn: Conn,
    connected_index: u16,
}
impl ConnEntry {
    const NON_EDGE: ConnEntry = ConnEntry {
        conn: Conn::No,
        connected_index: u16::MAX,
    };
    const NO_CONNECT: ConnEntry = ConnEntry {
        conn: Conn::No,
        connected_index: u16::MAX - 1,
    };
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    // mosaics with <= this number of crossings will not be saved
    // for 5 crossings, we don't need anything <= 5
    // for 4 crossings, anything <=2
    // set to zero to include all mosaics
    let discard_crossings: usize = 0;
    let size: usize = 1;
    let output_folder = "../data/1_toric";
    let max_lines = 50_000;
    create_dir_all(output_folder)?;
    let mut outbuf = RollingBufWriter::new(output_folder, max_lines)?;

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
    let mut mosaic_ct = 0;
    let mut mosaic = Mosaic::new(size, var);
    let len = mosaic.len;
    let mut branches: Vec<Vec<u8>> = vec![vec![]; len];
    let mut depth = 0;
    branches[0] = Vec::from(mosaic.get_valid_tiles(0));
    branches[0].reverse(); // this just preserves numeric order of the output
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
        while depth < len {
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
            let res = write_mosaic(out_buff, &mosaic)?;
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

fn write_mosaic(output_writer: &mut RollingBufWriter, mosaic: &Mosaic) -> Result<RollOver> {
    output_writer.write_line(
        &mosaic
            .data // get raw values
            .iter() // for each item in the mosaic
            .map(|val| format!("{:x}", val)) // format it as hex
            .collect::<Vec<String>>() // re-collect into a vector of strings?
            .join(""), // join into contiguous string
    )
}

// removing any mosaics with a row loop.
// with: get through first 50 million in 54.3 seconds. storing ~175k
// without: get through first 50 million in 45 seconds, but store ~322k
fn has_loop(mosaic: &Mosaic) -> bool {
    let sz = mosaic.size;
    'row_loop: for row in 0..sz {
        for col in 0..sz {
            let item = mosaic.get_tile_xy(col, row);
            if !matches!(item, 5 | 9 | 10) {
                // contine to next row if any item doesn't have a horizontal connection
                continue 'row_loop;
            }
        }
        return true;
    }
    false
}
