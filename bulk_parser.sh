./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 2
./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 3_bent
./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 3_line
./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 4_line
./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 4_t
./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 5
./main.py parse 3 cubic --no-clean-exit --keep-existing --cubic-version 6

./main.py merge cubic --cubic-version 2
./main.py merge cubic --cubic-version 3_line
./main.py merge cubic --cubic-version 3_bent
./main.py merge cubic --cubic-version 4_line
./main.py merge cubic --cubic-version 4_t
./main.py merge cubic --cubic-version 5
./main.py merge cubic --cubic-version 6
