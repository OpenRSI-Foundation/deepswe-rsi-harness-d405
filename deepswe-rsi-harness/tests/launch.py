"""Import only the injected, read-only evaluator root."""
import sys
sys.path.insert(0, "/tests")
from evaluate import main
main()
