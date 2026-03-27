use std::ops::Not;

use crate::conn_table::*;
use crate::*;

#[derive(Clone, Copy, PartialEq)]
pub enum Conn {
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
    connected_to: u16,
}
impl ConnEntry {
    const NON_EDGE: ConnEntry = ConnEntry {
        conn: Conn::No,
        connected_to: u16::MAX,
    };
    const NO_CONNECT: ConnEntry = ConnEntry {
        conn: Conn::No,
        connected_to: u16::MAX - 1,
    };
}
struct XYSide {
    x: usize,
    y: usize,
    side: Side,
}
pub struct Mosaic {
    tiles: Vec<u8>,
    edges: Vec<ConnEntry>,
    variant: MosaicVariant,
    size: usize, // grid square size
    len: usize,  // number of tiles
}
impl Mosaic {
    pub fn new(size: usize, variant: MosaicVariant) -> Mosaic {
        use MosaicVariant as M;
        let len = match &variant {
            M::Cubic { .. } => size * size * 6,
            _ => size * size,
        };
        assert!(len < (u16::MAX - 1) as usize, "Mosaic size is too big");

        let mut mos = Mosaic {
            tiles: vec![11; len],
            edges: vec![ConnEntry::NON_EDGE; len * 4],
            variant,
            size,
            len,
        };
        use MosaicVariant as MV;
        match mos.variant {
            MV::Flat => {
                mos.link_top_bottom(true);
                mos.link_left_right(true);
            }
            MV::Cylindrical => {
                mos.link_top_bottom(true);
                mos.link_left_right(false);
            }
            MV::Toric => {
                mos.link_top_bottom(false);
                mos.link_left_right(false);
            }
            MV::Cubic { .. } => {
                link_cubic_sides(&mut mos);
            }
            _ => todo!("Other types not implemented"),
        };
        if let MosaicVariant::Cubic { cubic_type } = &mos.variant {
            let non_zero_sides = cubic_from_name(cubic_type).unwrap().sides;
            for i in 0..mos.tiles.len() {
                let side_num = mos.cubic_get_side_num(i);
                // for each tile not on the face for this cubic type
                if !non_zero_sides.contains(&side_num) {
                    mos.set_tile(i, 12);
                }
            }
        }
        mos
    }

    pub fn set_tile(&mut self, index: usize, tile: u8) {
        // never change 'locked empty' tiles
        if self.tiles[index] == 12 {
            return;
        }
        self.tiles[index] = tile;
        for (i, conn) in TILE_CONNECTION_SIDES[tile as usize].iter().enumerate() {
            let edge_ind = index * 4 + i;
            let conn_ind = self.edges[edge_ind].connected_to as usize;
            // if it's an edge connection, and
            // only clear the connection when the current tile is < the tile it's connected to,
            // because tiles > than current are gaurunteed to be unset(=11)
            // connections are only set
            if self.is_valid_edge(conn_ind) && (edge_ind < conn_ind) {
                self.edges[edge_ind].conn = *conn;
                self.edges[conn_ind].conn = *conn;
            }
        }
    }
    pub fn get_valid_tiles(&self, index: usize) -> &'static [u8] {
        if self.tiles[index] == 12 {
            // will always be no connections, no matter what it's next to.
            return &[0];
        }
        let right = self.get_neighbor_conn(index, Side::Right) as usize;
        let up = self.get_neighbor_conn(index, Side::Up) as usize;
        let left = self.get_neighbor_conn(index, Side::Left) as usize;
        let down = self.get_neighbor_conn(index, Side::Down) as usize;
        let hash = down * 27 + left * 9 + up * 3 + right;
        CONNS_TO_VALID_TILES[hash]
    }
    /// returns true for any mosaics with a row that is a simple loop.
    #[allow(unused)]
    pub fn has_loop(&self) -> bool {
        if matches!(self.variant, MosaicVariant::Cubic { .. }) {
            todo!("Not Implemented for  cubic");
        }
        let sz = self.size;
        'row_loop: for row in 0..sz {
            for col in 0..sz {
                let item = self.get_tile_xy(col, row);
                if !matches!(item, 5 | 9 | 10) {
                    // contine to next row if any item doesn't have a horizontal connection
                    continue 'row_loop;
                }
            }
            return true;
        }
        false
    }
    pub fn get_len(&self) -> usize {
        self.len
    }
    fn is_valid_edge(&self, edge_ind: usize) -> bool {
        edge_ind < self.edges.len()
    }
    fn index_to_xy(&self, mut index: usize) -> (usize, usize) {
        if !matches!(self.variant, MosaicVariant::Cubic { .. }) {
            let col = index % self.size;
            let row = index / self.size;
            return (col, row);
        }
        // handle cubic
        if index < (self.len / 2) {
            let col = index % (self.size * 3);
            let row = index / (self.size * 3);
            return (col, row);
        }
        index -= self.len / 2;
        let col = index % self.size + self.size;
        let row = (index / self.size) + self.size;
        (col, row)
    }
    fn index_from_xy(&self, mut x: usize, mut y: usize) -> usize {
        if !matches!(self.variant, MosaicVariant::Cubic { .. }) {
            return y * self.size + x;
        }
        // handle cubic
        if y < self.size {
            return y * (self.size * 3) + x;
        }
        // for lower half of cubic, convert coords
        // to put 0,0 in top left of side 3
        x -= self.size;
        y -= self.size;
        self.size.pow(2) * 3 + y * self.size + x
    }
    fn get_tile_xy(&self, x: usize, y: usize) -> u8 {
        self.tiles[self.index_from_xy(x, y)]
    }
    fn get_neighbor_conn(&self, index: usize, side: Side) -> Conn {
        // Check if this edge is on the border
        let edge_conn = self.edges[index * 4 + side as usize];
        if edge_conn != ConnEntry::NON_EDGE {
            return edge_conn.conn;
        }
        // do calculation for interior edges
        let (x, y) = self.index_to_xy(index);
        match side {
            Side::Right => {
                let tile_ind = self.index_from_xy(x + 1, y);
                match self.tiles[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 2 | 3 | 6 | 12 => Conn::No,
                    _ => Conn::Yes,
                }
            }
            Side::Up => {
                let tile_ind = self.index_from_xy(x, y - 1);
                match self.tiles[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 3 | 4 | 5 | 12 => Conn::No,
                    _ => Conn::Yes,
                }
            }
            Side::Left => {
                let tile_ind = self.index_from_xy(x - 1, y);
                match self.tiles[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 1 | 4 | 6 | 12 => Conn::No,
                    _ => Conn::Yes,
                }
            }
            Side::Down => {
                let tile_ind = self.index_from_xy(x, y + 1);
                match self.tiles[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 1 | 2 | 5 | 12 => Conn::No,
                    _ => Conn::Yes,
                }
            }
        }
    }
    fn cubic_get_side_num(&self, index: usize) -> usize {
        let (x, y) = self.index_to_xy(index);
        let (x, y) = (x / self.size, y / self.size);
        match (x, y) {
            (x, 0) => x,
            (1, y) => y + 2,
            _ => panic!("Implementation Error"),
        }
    }
    /// Links edges moveing clockwise from edge1, counterclockwise from edge2
    fn link_edges(&mut self, mut edge1: XYSide, mut edge2: XYSide, close: bool) {
        // Given 2 starting edges, travelling clockwise along the first and
        // counter-clockwise along the second will make them match properly
        // moving to the right of the side specified

        // doing it this way to prevent x/y indexes from going <0
        let mut i = 0;
        loop {
            let ind1 = self.edge_index(&edge1);
            let ind2 = self.edge_index(&edge2);
            assert!(ind1 < self.edges.len());
            assert!(ind2 < self.edges.len());
            if close {
                self.edges[ind1] = ConnEntry::NO_CONNECT;
                self.edges[ind2] = ConnEntry::NO_CONNECT;
            } else {
                self.edges[ind1] = ConnEntry {
                    conn: Conn::Maybe,
                    connected_to: ind2 as u16,
                };
                self.edges[ind2] = ConnEntry {
                    conn: Conn::Maybe,
                    connected_to: ind1 as u16,
                };
            }
            i += 1;
            if i == self.size {
                break;
            }
            match edge1.side {
                // moving to the right of the side
                Side::Right => edge1.y += 1,
                Side::Up => edge1.x += 1,
                Side::Left => edge1.y -= 1,
                Side::Down => edge1.x -= 1,
            }
            match edge2.side {
                // moving to the right of the side
                Side::Right => edge2.y -= 1,
                Side::Up => edge2.x -= 1,
                Side::Left => edge2.y += 1,
                Side::Down => edge2.x += 1,
            }
        }
    }

    fn link_top_bottom(&mut self, close: bool) {
        let max_ind = self.size - 1;
        self.link_edges(
            XYSide {
                x: 0,
                y: 0,
                side: Side::Up,
            },
            XYSide {
                x: 0,
                y: max_ind,
                side: Side::Down,
            },
            close,
        );
    }
    fn link_left_right(&mut self, close: bool) {
        let max_ind = self.size - 1;
        self.link_edges(
            XYSide {
                x: 0,
                y: max_ind,
                side: Side::Left,
            },
            XYSide {
                x: max_ind,
                y: max_ind,
                side: Side::Right,
            },
            close,
        );
    }
    fn edge_index(&self, edge: &XYSide) -> usize {
        self.index_from_xy(edge.x, edge.y) * 4 + edge.side as usize
    }
}
impl std::fmt::Display for Mosaic {
    /// Formats the mosaic into a string
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            self.tiles
                .iter()
                .map(|val| format!("{:x}", val))
                .collect::<String>()
        )
    }
}
/// Constructs the edge connections for cubic mosaics
fn link_cubic_sides(mos: &mut Mosaic) {
    use Side::*;
    let sz = mos.size;
    if let MosaicVariant::Cubic { cubic_type } = &mos.variant {
        let sides = cubic_from_name(cubic_type).unwrap().sides;
        // 0 top to 5 left
        mos.link_edges(
            XYSide {
                x: 0,
                y: 0,
                side: Up,
            },
            XYSide {
                x: sz,
                y: sz * 3,
                side: Left,
            },
            // only link the sides if sides 0 and 5 are both used in this cubic-type
            ([0, 5].iter().all(|a| sides.contains(a))).not(),
        );
        // 1 top to 5 bottom
        mos.link_edges(
            XYSide {
                x: sz,
                y: 0,
                side: Up,
            },
            XYSide {
                x: sz,
                y: sz * 4 - 1,
                side: Down,
            },
            ([1, 5].iter().all(|a| sides.contains(a))).not(),
        );
        // 0 left to 4 left
        mos.link_edges(
            XYSide {
                x: 0,
                y: sz - 1,
                side: Left,
            },
            XYSide {
                x: sz,
                y: sz * 2,
                side: Left,
            },
            ([0, 4].iter().all(|a| sides.contains(a))).not(),
        );
        // 3 left to 0 bottom
        mos.link_edges(
            XYSide {
                x: sz,
                y: sz * 2 - 1,
                side: Left,
            },
            XYSide {
                x: 0,
                y: sz - 1,
                side: Down,
            },
            ([3, 0].iter().all(|a| sides.contains(a))).not(),
        );
        // 2 bottom to 3 right
        mos.link_edges(
            XYSide {
                x: sz * 3 - 1,
                y: sz - 1,
                side: Down,
            },
            XYSide {
                x: sz * 2 - 1,
                y: sz * 2 - 1,
                side: Right,
            },
            ([2, 3].iter().all(|a| sides.contains(a))).not(),
        );
        // 4 right to 2 right
        mos.link_edges(
            XYSide {
                x: 2 * sz - 1,
                y: 2 * sz,
                side: Right,
            },
            XYSide {
                x: 3 * sz - 1,
                y: sz - 1,
                side: Right,
            },
            ([4, 2].iter().all(|a| sides.contains(a))).not(),
        );
        // 5 right to 2 top
        mos.link_edges(
            XYSide {
                x: 2 * sz - 1,
                y: 3 * sz,
                side: Right,
            },
            XYSide {
                x: 3 * sz - 1,
                y: 0,
                side: Up,
            },
            ([5, 2].iter().all(|a| sides.contains(a))).not(),
        );
    }
}
