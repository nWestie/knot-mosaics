
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

pub const CONNECTION_TABLE: &[&[u8]] = &[
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
