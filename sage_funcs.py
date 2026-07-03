from sage.all import Link  # type:ignore
from multiprocessing import Process, Queue

def make_knot(pd_codes: list[list[int]])->Link:
    """This is broken out into it's own file to prevent import Errors. The Tkinter visualizer doesn't scale correctly in WSL, and sage cannot install on windows, so the visualizer is run in a separate windows venv. However, this means that sage cannot be on the import path for the visualizer."""
    return Link(pd_codes)


def _worker(knot, q):
    try:
        q.put(str(knot.get_knotinfo(unique=False)))
    except Exception:
        q.put(None)

def get_knotinfo_with_timeout(knot, timeout=30)->str|None:
    """Runs get_knotinfo() in another thread so it can be force-killed if needed. Timeout in seconds"""
    q = Queue()
    p = Process(target=_worker, args=(knot, q))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return None
    return q.get() if not q.empty() else None