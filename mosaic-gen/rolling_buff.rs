use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::{Path, PathBuf};

pub struct RollingBufWriter {
    base_path: PathBuf,
    pub max_lines: usize,
    current_lines: usize,
    file_index: usize,
    writer: BufWriter<File>,
}
pub enum RollOver {
    Rolled(usize),
    NoRollover,
}

impl RollingBufWriter {
    pub fn new<P: AsRef<Path>>(base_path: P, max_lines: usize) -> io::Result<Self> {
        let base_path = base_path.as_ref().to_path_buf();
        let writer = Self::open_file(&base_path, 0)?;

        Ok(Self {
            base_path,
            max_lines,
            current_lines: 0,
            file_index: 0,
            writer,
        })
    }

    fn open_file(base_path: &Path, index: usize) -> io::Result<BufWriter<File>> {
        let path = base_path.with_extension(format!("{index}.txt"));
        let file = File::create(path)?;
        Ok(BufWriter::new(file))
    }

    fn roll(&mut self) -> io::Result<()> {
        self.writer.flush()?;
        self.file_index += 1;
        self.current_lines = 0;
        self.writer = Self::open_file(&self.base_path, self.file_index)?;
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
