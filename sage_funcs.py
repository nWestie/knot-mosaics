from sage.all import Link  # type:ignore

def make_knot(pd_codes: list[list[int]])->Link:
    """This is broken out into it's own file to prevent import Errors. The Tkinter visualizer doesn't scale correctly in WSL, and sage cannot install on windows, so the visualizer is run in a separate windows venv. However, this means that sage cannot be on the import path for the visualizer."""
    return Link(pd_codes)