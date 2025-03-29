import argparse
from pathlib import Path

import formatter
import grammar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help='Path of MATLAB .m file')

    args = parser.parse_args()
    file_path = Path(args.path)

    print(f'Formatting file "{file_path}" ...')
    file_model = grammar.parse_file(file_path)
    formatter.format_file(file_model)
    file_path.with_stem(file_path.stem + "_fmt").write_text(str(file_model))
    print("Done!")


if __name__ == "__main__":
    main()
