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
pub struct Mosaic {
    data: Vec<u8>,
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

        let mut edges = vec![ConnEntry::NON_EDGE; len * 4];
        use MosaicVariant as MV;
        edges = match variant {
            MV::Flat => {
                edges = close_top_bottom(edges, size);
                close_sides(edges, size, size)
            }
            MV::Cylindrical => {
                edges = close_top_bottom(edges, size);
                link_sides(edges, size, size)
            }
            MV::Toric => {
                edges = link_top_bottom(edges, size);
                link_sides(edges, size, size)
            }
            _ => todo!("Other types not implemented"),
        };
        Mosaic {
            data: vec![11; len],
            edges,
            variant,
            size,
            len,
        }
    }

    pub fn set_tile(&mut self, index: usize, tile: u8) {
        self.data[index] = tile;
        for (i, conn) in TILE_CONNECTION_SIDES[tile as usize].iter().enumerate() {
            let edge_ind = index * 4 + i;
            let conn_ind = self.edges[edge_ind].connected_index as usize;
            // if it's an edge connection, and
            // only clear the connection when the current tile is < the tile it's connected to,
            // because tiles > than current are gaurunteed to be unset(=11)
            // connections are only set
            if (conn_ind < self.len * 4) && (edge_ind < conn_ind) {
                self.edges[edge_ind].conn = *conn;
                self.edges[conn_ind].conn = *conn;
            }
        }
    }
    pub fn get_valid_tiles(&self, index: usize) -> &'static [u8] {
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
    fn index_to_xy(&self, index: usize) -> (usize, usize) {
        if !matches!(self.variant, MosaicVariant::Cubic { .. }) {
            let col = index % self.size;
            let row = index / self.size;
            return (col, row);
        }
        // handle cubic
        todo!("Handle Cubic")
    }
    fn index_from_xy(&self, x: usize, y: usize) -> usize {
        if !matches!(self.variant, MosaicVariant::Cubic { .. }) {
            return y * self.size + x;
        }
        // handle cubic
        todo!("Handle Cubic")
    }
    fn get_tile_xy(&self, x: usize, y: usize) -> u8 {
        self.data[self.index_from_xy(x, y)]
    }
    fn get_neighbor_conn(&self, index: usize, side: Side) -> Conn {
        // Check if this edge is on the border
        let edge_conn = self.edges[index * 4 + side as usize];
        if edge_conn != ConnEntry::NON_EDGE {
            return edge_conn.conn;
        }
        let (x, y) = self.index_to_xy(index);
        match side {
            Side::Right => {
                let tile_ind = self.index_from_xy(x + 1, y);
                match self.data[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 2 | 3 | 6 => Conn::No,
                    _ => Conn::Yes,
                }
            }
            Side::Up => {
                let tile_ind = self.index_from_xy(x, y - 1);
                match self.data[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 3 | 4 | 5 => Conn::No,
                    _ => Conn::Yes,
                }
            }
            Side::Left => {
                let tile_ind = self.index_from_xy(x - 1, y);
                match self.data[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 1 | 4 | 6 => Conn::No,
                    _ => Conn::Yes,
                }
            }
            Side::Down => {
                let tile_ind = self.index_from_xy(x, y + 1);
                match self.data[tile_ind] {
                    11 => Conn::Maybe,
                    0 | 1 | 2 | 5 => Conn::No,
                    _ => Conn::Yes,
                }
            }
        }
    }
}
impl std::fmt::Display for Mosaic {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}",
            self.data
                .iter()
                .map(|val| format!("{:x}", val))
                .collect::<String>()
        )
    }
}

fn edge_index(index: usize, side: Side) -> usize {
    index * 4 + side as usize
}
fn close_top_bottom(mut edges: Vec<ConnEntry>, width: usize) -> Vec<ConnEntry> {
    let last_row = edges.len() / 4 - width;
    for i in 0..width {
        edges[edge_index(i, Side::Up)] = ConnEntry::NO_CONNECT;
        edges[edge_index(last_row + i, Side::Down)] = ConnEntry::NO_CONNECT;
    }
    edges
}
fn close_sides(mut edges: Vec<ConnEntry>, width: usize, height: usize) -> Vec<ConnEntry> {
    for row in 0..height {
        edges[edge_index(row * width, Side::Left)] = ConnEntry::NO_CONNECT;
        edges[edge_index(row * width + width - 1, Side::Right)] = ConnEntry::NO_CONNECT;
    }
    edges
}
fn link_sides(mut edges: Vec<ConnEntry>, width: usize, height: usize) -> Vec<ConnEntry> {
    for row in 0..height {
        let left_ind = edge_index(row * width, Side::Left);
        let right_ind = edge_index(row * width + width - 1, Side::Right);
        edges[left_ind] = ConnEntry {
            conn: Conn::Maybe,
            connected_index: right_ind as u16,
        };
        edges[right_ind] = ConnEntry {
            conn: Conn::Maybe,
            connected_index: left_ind as u16,
        };
    }
    edges
}
fn link_top_bottom(mut edges: Vec<ConnEntry>, width: usize) -> Vec<ConnEntry> {
    let last_row = edges.len() / 4 - width;
    for col in 0..width {
        let top_ind = edge_index(col, Side::Up);
        let bottom_ind = edge_index(last_row + col, Side::Right);
        edges[top_ind] = ConnEntry {
            conn: Conn::Maybe,
            connected_index: bottom_ind as u16,
        };
        edges[bottom_ind] = ConnEntry {
            conn: Conn::Maybe,
            connected_index: top_ind as u16,
        };
    }
    edges
}
