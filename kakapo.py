import argparse
from pathlib import Path

import pyparsing

import formatter
import grammar


def format_file(file_path: Path):
    print(f'{file_path}')
    try:
        file_model = grammar.parse_file(file_path)
    except pyparsing.ParseException as e:
        print("SQUAWK!", e)
        return False
    formatter.format_file(file_model)
    file_path.write_text(str(file_model))
    return True


def main():
    parser = argparse.ArgumentParser(prog="Kakapo", description="A flightless MATLAB formatter")
    parser.add_argument('path', type=str, help='Path of MATLAB .m file or directory')

    args = parser.parse_args()
    path = Path(args.path)

    success = True

    if path.is_file():
        success = format_file(path)
    elif path.is_dir():
        for file_path in path.glob("**/*.m"):
            success = format_file(file_path)
    if success:
        print("Ching!")


if __name__ == "__main__":
    main()
