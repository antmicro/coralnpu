import argparse
import sys
from pathlib import Path
from typing import Union

def main():
    output_file = sys.argv[0]

    # TODO: write batch list creation logic from run_uvm_regression.py
    with open(output_file, 'w') as f_list:
        for t in pending_targets:
            info = test_info_map[t]
            f_list.write(f"{info['elf']} {info['tohost']:08x} {info['entry']:08x} {info['timeout']} {info['spike']} {t}\n")

if __name__ == '__main__':
    main()
