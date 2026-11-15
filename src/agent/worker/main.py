import logging
import signal
import threading

from sqlalchemy import text

from agent.db import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
stop = threading.Event()


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log.info("Foundation worker started; durable job processing begins in Stage 1")
    while not stop.is_set():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            log.exception("Database health check failed")
        stop.wait(10)


if __name__ == "__main__":
    main()

