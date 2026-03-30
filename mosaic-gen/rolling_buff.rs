use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::{Path, PathBuf};

pub struct RollingBufWriter {
    output_dir: PathBuf,
    pub max_lines: usize,
    current_lines: usize,
    file_index: usize,
    buf_size: usize,
    writer: BufWriter<File>,
}
pub enum RollOver {
    Rolled(usize),
    NoRollover,
}

impl RollingBufWriter {
    pub fn new<P: AsRef<Path>>(
        base_path: &P,
        max_lines: usize,
        line_len: usize,
    ) -> io::Result<Self> {
        let base_path = base_path.as_ref().to_path_buf();
        let buf_size = line_len * 2000;
        let writer = Self::open_file(&base_path, 0, buf_size)?;
        Ok(Self {
            output_dir: base_path,
            max_lines,
            current_lines: 0,
            file_index: 0,
            buf_size,
            writer,
        })
    }

    fn open_file(base_path: &Path, index: usize, buf_size: usize) -> io::Result<BufWriter<File>> {
        let path = base_path.join(format!("pt{index:04}.txt"));
        let file = File::create(path)?;
        Ok(BufWriter::with_capacity(buf_size, file))
    }

    fn roll(&mut self) -> io::Result<()> {
        self.writer.flush()?;
        self.file_index += 1;
        self.current_lines = 0;
        self.writer = Self::open_file(&self.output_dir, self.file_index, self.buf_size)?;
        Ok(())
    }

    pub fn write_line(&mut self, line: &str) -> io::Result<RollOver> {
        let rolled = if self.current_lines >= self.max_lines {
            self.roll()?;
            RollOver::Rolled(self.file_index)
        } else {
            RollOver::NoRollover
        };

        writeln!(self.writer, "{}", line)?;

        self.current_lines += 1;
        Ok(rolled)
    }
    pub fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()
    }
}
