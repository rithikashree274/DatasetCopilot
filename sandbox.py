import sys
from core import sandbox_utils

def main():
    if len(sys.argv) < 2:
        print("Usage: python sandbox.py <code_file.py>")
        sys.exit(1)
    code_file = sys.argv[1]
    try:
        with open(code_file, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(f"Failed to read file {code_file}: {e}")
        sys.exit(1)
    result = sandbox_utils.run_code_in_sandbox(code, work_dir="app/assets/data")
    print(result["output"])
    if not result["success"]:
        sys.exit(2)

if __name__ == "__main__":
    main()
