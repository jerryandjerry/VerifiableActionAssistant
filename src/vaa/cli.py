from __future__ import annotations

import argparse
import os


def cli() -> None:
    parser = argparse.ArgumentParser(prog="vaa")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="run the API and demo UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    serve.add_argument("--reload", action="store_true")

    subparsers.add_parser("reset", help="reset and seed the demo database")
    args = parser.parse_args()

    if args.command in {None, "serve"}:
        import uvicorn

        uvicorn.run(
            "vaa.main:app",
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8000),
            reload=getattr(args, "reload", False),
        )
        return

    if args.command == "reset":
        os.environ.setdefault("VAA_AUTO_SEED", "true")
        from vaa.seed import main

        main()
