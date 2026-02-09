#![allow(unused)]

use dialoguer::Input;
use std::collections::HashSet;
use std::fs::{File, create_dir_all};
use std::io::{BufWriter, Result, Write};
use std::time::Instant;
mod conn_table;
mod rolling_buff;
use format_num::format_num;
use rolling_buff::{RollOver, RollingBufWriter};
struct Mosaic {
    data: Vec<u8>,
    size: usize,
}
impl Mosaic {
    fn new(size: usize) -> Mosaic {
        Mosaic {
            data: vec![11; size * size],
            size,
        }
    }
    fn crossing_ct(&self) -> usize {
        let mut ct = 0;
        for tile in &self.data {
            if tile > &9u8 {
                ct += 1
            };
        }
        ct
    }
    fn get(&self, x: usize, y: usize) -> u8 {
        self.data[y * self.size + x]
    }
    fn get_linear(&self, ind: usize) -> u8 {
        self.data[ind]
    }
    fn set(&mut self, x: usize, y: usize, tile: u8) {
        self.data[(y * self.size + x)] = tile;
    }
    fn set_linear(&mut self, ind: usize, tile: u8) {
        self.data[ind] = tile;
    }
    fn right_tile(&self, mut x: usize, y: usize) -> u8 {
        x = (x + 1) % self.size;
        self.get(x, y)
    }
    fn left_tile(&self, mut x: usize, y: usize) -> u8 {
        x = (x + self.size - 1) % self.size;
        self.get(x, y)
    }
    fn up_tile(&self, x: usize, y: usize) -> u8 {
        match y {
            0 => 0,
            y => self.get(x, y - 1),
        }
    }
    fn down_tile(&self, x: usize, y: usize) -> u8 {
        match y + 1 {
            new_y if new_y == self.size => 0,
            new_y => self.get(x, new_y),
        }
    }
    fn up_tile_toric(&self, x: usize, y: usize) -> u8 {
        match y {
            0 => self.get(x, self.size - 1),
            y => self.get(x, y - 1),
        }
    }
    fn down_tile_toric(&self, x: usize, y: usize) -> u8 {
        match y + 1 {
            new_y if new_y == self.size => self.get(x, 0),
            new_y => self.get(x, new_y),
        }
    }
}

fn main() -> Result<()> {
    // let size: usize = Input::new()
    // .with_prompt("Size of generated mosaics?")
    // .interact_text()
    // .unwrap();

    // let output_path: String = Input::new()
    //     .with_prompt("Path to Write Mosaics To?")
    //     .interact_text()
    //     .unwrap();
    
    let size: usize = 4;
    // mosaics with <= this number of crossings will not be saved
    // for 5 crossings, we don't need anything under 6
    // for 4 crossings, anything <=2
    let discard_crossings: usize = 2;
    let output_folder = "../data/4_cyl";
    create_dir_all(output_folder)?;
    let mut outbuf = RollingBufWriter::new(output_folder, 100_000)?;

    let now = Instant::now(); //Timing 

    println!("generating ...");
    mosaic_gen(&mut outbuf, size, discard_crossings)?;
    print!(
        "Generation complete! ({:.6} s)",
        now.elapsed().as_secs_f64()
    );
    outbuf.flush()?;
    Ok(())
}

fn mosaic_gen(out_buff: &mut RollingBufWriter, size: usize, trim_crossings: usize) -> Result<()> {
    let vector_length = size * size - 1;
    // let mut mosaic: Vec<u8> = vec![11; vector_length + 1]; // 11 is not a valid tile
    let mut mosaic: Mosaic = Mosaic::new(size);
    let mut curr_tile: usize = 0;
    let mut rightward = true;
    let mut digit_index: Vec<usize> = vec![0; vector_length + 1]; // I think this is the index into valid_tiles for each tile
    let mut valid_tiles_for: Vec<&[u8]> = vec![&[]; vector_length + 1];
    let mut mosaic_ct: u64 = 0;
    loop {
        if rightward {
            // calculate the base3 number for
            valid_tiles_for[curr_tile] = calc_valid_tiles(&mosaic, curr_tile, size);
            // this is where we back our way up the tree
            if valid_tiles_for[curr_tile].is_empty() {
                rightward = false;
                curr_tile -= 1;
                continue;
            }
            digit_index[curr_tile] = 1;
            mosaic.set_linear(curr_tile, valid_tiles_for[curr_tile][0]);
            if curr_tile == vector_length {
                // if we're done the first pass of filling the matrix
                rightward = false;
                continue;
            }
            curr_tile += 1;
            continue;
        }
        // if not rightward
        if (curr_tile == vector_length) {
            mosaic_ct += 1;
            if mosaic.crossing_ct() <= trim_crossings || has_loop(&mosaic) {
                // if mosaic.crossing_ct() <= trim_crossings {
                // don't bother recording any with low crossings,
                // we know these have a mosaic number under what we're working on
            } else if let RollOver::Rolled(index) = write_mosaic(out_buff, &mosaic)? {
                println!(
                    "on pt{index} - {} generated, {} saved",
                    format_num!(",.3s", mosaic_ct as f64),
                    format_num!(",.3s", (out_buff.max_lines * index) as f64)
                );
            }
            // if mosaic_ct > 50_000_000{
            //     break; // stop here for testing, after 50 million are generated
            // }
        }

        // if we already wrote a matrix with the last valid tile in this
        if digit_index[curr_tile] == valid_tiles_for[curr_tile].len() {
            if curr_tile == 0 {
                break; // this is the exit condition for the program: we've exhausted our way back to the 0th tile
            }
            mosaic.set_linear(curr_tile, 11);
            curr_tile -= 1;
            continue;
        }

        //Move to next tile in list for current tile, then continue rightward to fill the rest of the matrix
        mosaic.set_linear(
            curr_tile,
            valid_tiles_for[curr_tile][digit_index[curr_tile]],
        );
        digit_index[curr_tile] += 1;
        if curr_tile < vector_length {
            curr_tile += 1;
            rightward = true;
        }
    }

    Ok(())
}

fn calc_valid_tiles(mosaic: &Mosaic, curr_tile: usize, size: usize) -> &'static [u8] {
    //Find valid tiles for current tile based on surroundings
    let curr_x = curr_tile % size;
    let curr_y = curr_tile / size;

    let right_tile = mosaic.right_tile(curr_x, curr_y);
    let left_tile = mosaic.left_tile(curr_x, curr_y);
    let up_tile = mosaic.up_tile(curr_x, curr_y);
    let down_tile = mosaic.down_tile(curr_x, curr_y);

    let hash = match right_tile {
        //right tile
        11 => 2,
        0 | 2 | 3 | 6 => 0,
        _ => 1,
    } + 3 * match up_tile {
        //up
        11 => 2,
        0 | 3 | 4 | 5 => 0,
        _ => 1,
    } + 9 * match left_tile {
        //left
        11 => 2,
        0 | 1 | 4 | 6 => 0,
        _ => 1,
    } + 27
        * match down_tile {
            //down
            11 => 2,
            0 | 1 | 2 | 5 => 0,
            _ => 1,
        };
    conn_table::CONNECTION_TABLE[hash]
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
            let item = mosaic.get(col, row);
            if !matches!(item, 5 | 9 | 10) {
                // contine to next row if any item doesn't have a horizontal connection
                continue 'row_loop;
            }
        }
        return true;
    }
    false
}
