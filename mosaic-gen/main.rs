use dialoguer::Input;
use std::fs::File;
use std::io::{BufWriter, Result, Write};
use std::time::Instant;

//Connection table for mosaic generation
//Essentially a lazy hash map, states of surrounding tiles are converted to a base-3 number:
// 0: no connection to current tile
// 1: must connect to current tile
// 2: undecided, may or may not connect
//
// Digits in the number are assigned as below:
//    1
// 2 ▇▇ 0
//    3

// Ex - if the tile has a connection to the top, and is undecided on the bottom,
// with no left/right conneciton, it would have a hash of 2010(base3) = 2*3^3 + 1*3 = 21

static CONNECTION_TABLE: &[&[usize]] = &[
    //000x (base3)
    &[0],
    &[],
    &[0],
    //001x
    &[],
    &[3],
    &[3],
    //002x
    &[0],
    &[3],
    &[0, 3],
    //010x
    &[],
    &[5],
    &[5],
    //011x
    &[4],
    &[],
    &[4],
    //012x
    &[4],
    &[5],
    &[4, 5],
    //020x
    &[0],
    &[5],
    &[0, 5],
    //021x
    &[4],
    &[3],
    &[3, 4],
    //022x
    &[0, 4],
    &[3, 5],
    &[0, 3, 4, 5],
    //100x
    &[],
    &[2],
    &[2],
    //101x
    &[6],
    &[],
    &[6],
    //102x
    &[6],
    &[2],
    &[2, 6],
    //110x
    &[1],
    &[],
    &[1],
    //111x
    &[],
    &[7, 8, 9, 10],
    &[7, 8, 9, 10],
    //112x
    &[1],
    &[7, 8, 9, 10],
    &[1, 7, 8, 9, 10],
    //120x
    &[1],
    &[2],
    &[1, 2],
    //121x
    &[6],
    &[7, 8, 9, 10],
    &[6, 7, 8, 9, 10],
    //122x
    &[6],
    &[2, 7, 8, 9, 10],
    &[2, 6, 7, 8, 9, 10],
    //200x
    &[0],
    &[2],
    &[0, 2],
    //201x
    &[6],
    &[3],
    &[3, 6],
    //202x
    &[0, 6],
    &[2, 3],
    &[0, 2, 3, 6],
    //210x
    &[1],
    &[5],
    &[1, 5],
    //211x
    &[4],
    &[7, 8, 9, 10],
    &[4, 7, 8, 9, 10],
    //212x
    &[1, 4],
    &[5, 7, 8, 9, 10],
    &[1, 5, 7, 8, 9, 10],
    //220x
    &[0, 1],
    &[2, 5],
    &[0, 1, 2, 5],
    //221x
    &[4, 6],
    &[3, 7, 8, 9, 10],
    &[3, 4, 5, 7, 8, 9, 10],
    //222x
    &[0, 1, 4, 6],
    &[2, 3, 5, 7, 8, 9, 10],
    &[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
];

fn main() -> Result<()> {
    // let size: usize = Input::new()
    // .with_prompt("Size of generated mosaics?")
    // .interact_text()
    // .unwrap();
    let size: usize = 1;

    // let output_path: String = Input::new()
    //     .with_prompt("Path to Write Mosaics To?")
    //     .interact_text()
    //     .unwrap();
    let output_path: &str = "../data/test.txt";
    let output_file = File::create(&output_path)?;
    let mut outbuf = BufWriter::new(output_file);

    let now = Instant::now(); //Timing 

    print!("generating ...\n");
    mosaic_gen(&mut outbuf, size)?;
    print!(
        "Generation complete! ({:.6} s)",
        now.elapsed().as_secs_f64()
    );
    outbuf.flush()?;
    Ok(())
}

fn mosaic_gen(output_buffer: &mut BufWriter<File>, size: usize) -> Result<()> {
    let vector_length = size * size - 1;
    let mut mosaic: Vec<usize> = vec![11; vector_length + 1]; // 11 is not a valid tile
    let mut curr_tile: usize = 0;
    let mut rightward = true;
    let mut digit_index: Vec<usize> = vec![0; vector_length + 1]; // I think this is the index into valid_tiles for each tile
    let mut valid_tiles_for = Vec::with_capacity(vector_length + 1);
    unsafe {
        valid_tiles_for.set_len(vector_length + 1);
    }

    loop {
        if rightward {
            //Find valid tiles for current tile based on surroundings
            let right_tile = mosaic[size * ((curr_tile) / size) + (curr_tile + 1) % size];
            let up_tile = mosaic[size * ((curr_tile / size + size - 1) % size) + curr_tile % size];
            let left_tile = mosaic[size * ((curr_tile) / size) + (curr_tile + size - 1) % size];
            let down_tile = mosaic[size * ((curr_tile / size + 1) % size) + curr_tile % size];

            // calculate the base3 number for 
            valid_tiles_for[curr_tile] = CONNECTION_TABLE[match right_tile {
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
                }];
            // this is where we back our way up the tree
            if valid_tiles_for[curr_tile].is_empty() {
                rightward = false;
                curr_tile -= 1;
                continue;
            }
            digit_index[curr_tile] = 1;
            mosaic[curr_tile] = valid_tiles_for[curr_tile][0];
            if curr_tile == vector_length {
                // if we're done the first pass of filling the matrix
                rightward = false;
                continue;
            }
            curr_tile += 1;
            continue;
        }
        // if not rightward
        if curr_tile == vector_length {
            write_mosaic(output_buffer, &mosaic)?;
        }

        // if we already wrote a matrix with the last valid tile in this  
        if digit_index[curr_tile] == valid_tiles_for[curr_tile].len() {
            if curr_tile == 0 {
                break; // this is the exit condition for the program: we've exhausted our way back to the 0th tile
            }
            mosaic[curr_tile] = 11;
            curr_tile -= 1;
            continue;
        }

        //Move to next tile in list for current tile, then continue rightward to fill the rest of the matrix
        mosaic[curr_tile] = valid_tiles_for[curr_tile][digit_index[curr_tile]];
        digit_index[curr_tile] += 1;
        if curr_tile < vector_length {
            curr_tile += 1;
            rightward = true;
        }
    }

    Ok(())
}

fn write_mosaic(output_buffer: &mut BufWriter<File>, mosaic: &[usize]) -> Result<()> {
    writeln!(
        // this kinda a mess ...
        output_buffer,
        "{}",
        mosaic
            .iter() // for each item in the mosaic
            .map(|val| format!("{:x}", val)) // format it as hex
            .collect::<Vec<String>>() // re-collect into a vector of strings?
            .join("") // join into contiguous string
    )?;
    Ok(())
}