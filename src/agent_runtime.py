"""Keep SDK async connections on one process-lifetime event loop across UI reruns."""
import asyncio
from concurrent.futures import TimeoutError
import threading

_lock = threading.Lock()
_loop = None


def run_agent(coroutine):
    global _loop
    with _lock:
        if _loop is None:
            ready = threading.Event()
            def serve():
                global _loop
                _loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_loop)
                ready.set()
                _loop.run_forever()
            threading.Thread(target=serve, daemon=True, name='dpe-agent-loop').start()
            ready.wait()
    future = asyncio.run_coroutine_threadsafe(coroutine, _loop)
    try:
        return future.result(timeout=240)
    except TimeoutError:
        future.cancel()
        raise RuntimeError('Agent request timed out') from None
