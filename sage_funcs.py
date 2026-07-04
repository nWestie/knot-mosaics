from sage.all import Link  # type: ignore
from multiprocessing import Process, Queue


def make_knot(pd_codes: list[list[int]]) -> Link:
    """This is broken out into it's own file to prevent import Errors. The Tkinter visualizer doesn't scale correctly in WSL, and sage cannot install on windows, so the visualizer is run in a separate windows venv. However, this means that sage cannot be on the import path for the visualizer."""
    knot = Link(pd_codes)
    new_knot = knot.simplify()
    # new_knot may be null if it cannot be simplified
    if new_knot:
        knot = new_knot
    return knot


def _worker(knot, q: Queue):
    try:
        q.put(knot.get_knotinfo(unique=False))
    except Exception:
        q.put(None)


def get_knotinfo_with_timeout(knot, timeout=30) -> str | None:
    """Runs get_knotinfo() in another thread so it can be force-killed if needed. Timeout in seconds"""
    queue = Queue()
    runner = Process(target=_worker, args=(knot, queue))
    runner.start()
    runner.join(timeout)
    if runner.is_alive():
        runner.terminate()
        runner.join()
        return None
    return queue.get() if not queue.empty() else None
