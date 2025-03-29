import argparse
from pathlib import Path

import formatter
import grammar


def main():
    file_path = Path(r"playground/matlabfrag/matlabfrag_short.m")
    file_model = grammar.parse_file(file_path)
    formatter.format_file(file_model)
    file_path.with_stem(file_path.stem + "_fmt").write_text(str(file_model))


if __name__ == "__main__":
    main()
