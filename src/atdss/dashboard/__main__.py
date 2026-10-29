"""Run the AT-DSS live dashboard: ``python -m atdss.dashboard``."""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from ..config import load_config
from .app import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Live synthetic arrival simulator dashboard for AT-DSS."
    )
    parser.add_argument("--config", default=None, help="Path to the airport YAML config.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--flights", type=int, default=100, help="Number of arrival flights.")
    parser.add_argument("--seed", type=int, default=42, help="Synthetic traffic seed.")
    parser.add_argument(
        "--strategy",
        default="fcfs",
        choices=("fcfs", "priority"),
        help="Sequencing strategy to visualize.",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=30.0,
        help="Arrival demand in flights per hour.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=60.0,
        help="Initial simulated seconds per wall-clock second.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the dashboard in the default browser after startup.",
    )
    parser.add_argument("--log-level", default="info", help="Uvicorn log level.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    app = create_app(
        config,
        flights=args.flights,
        seed=args.seed,
        strategy=args.strategy,
        rate=args.rate,
        speed=args.speed,
    )

    if args.open:
        browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
        url = f"http://{browser_host}:{args.port}"
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
