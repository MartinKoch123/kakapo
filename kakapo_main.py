import argparse
from pathlib import Path

import pyparsing

from kakapo import formatter


def format_file(file_path: Path):
    print(f'{file_path}')
    try:
        formatter.format_file(file_path)
    except pyparsing.ParseException as e:
        print("SQUAWK!", e)
        return False
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
