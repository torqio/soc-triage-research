#!/usr/bin/env bash
# Download the public GUIDE dataset (Kaggle "Microsoft Security Incident Prediction", dataset version 2) and
# verify its sha256 against the pre-registered value in configs/guide/selection.yaml.
# About 540 MB. The pipeline reads GUIDE_Train.csv and GUIDE_Test.csv straight from the archive, so nothing is
# unpacked (unpacked they take 3.5 GB; pass --extract to unpack them anyway).
#
# Kaggle serves this public dataset without an account. If an anonymous download is refused, the script falls
# back to the `kaggle` CLI (configured as usual) or to KAGGLE_USERNAME / KAGGLE_KEY in the environment.
# GUIDE is distributed by Microsoft under its own terms on Kaggle; it is not redistributed in this repository.
#
# Usage: scripts/guide/download.sh [--extract] [DEST_DIR]        (default: work/guide/raw)
set -euo pipefail
cd "$(dirname "$0")/../.."
EXTRACT=0
if [ "${1:-}" = "--extract" ]; then EXTRACT=1; shift; fi
DEST="${1:-work/guide/raw}"
REF="Microsoft/microsoft-security-incident-prediction"
URL="https://www.kaggle.com/api/v1/datasets/download/$REF?datasetVersionNumber=2"
WANT="$(sed -n 's/^ *archive_sha256: *//p' configs/guide/selection.yaml)"
ARCHIVE="$DEST/archive.zip"
mkdir -p "$DEST"

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

if [ -f "$ARCHIVE" ] && [ "$(sha256 "$ARCHIVE")" = "$WANT" ]; then
  echo "archive already downloaded and verified: $ARCHIVE"
else
  rm -f "$ARCHIVE.part"
  echo "downloading GUIDE (about 540 MB) to $ARCHIVE ..."
  if curl -fL --retry 3 --progress-bar -o "$ARCHIVE.part" "$URL"; then
    :
  elif [ -n "${KAGGLE_USERNAME:-}" ] && [ -n "${KAGGLE_KEY:-}" ]; then
    echo "anonymous download refused; retrying with KAGGLE_USERNAME / KAGGLE_KEY"
    curl -fL --retry 3 --progress-bar -u "$KAGGLE_USERNAME:$KAGGLE_KEY" -o "$ARCHIVE.part" "$URL"
  elif command -v kaggle >/dev/null; then
    echo "anonymous download refused; retrying with the kaggle CLI"
    kaggle datasets download -d "$REF" -p "$DEST" --force
    mv "$DEST/microsoft-security-incident-prediction.zip" "$ARCHIVE.part"
  else
    echo "download failed. Download the archive manually from https://www.kaggle.com/datasets/$REF" >&2
    echo "(version 2) and save it as $ARCHIVE, or set KAGGLE_USERNAME and KAGGLE_KEY." >&2
    exit 1
  fi
  mv "$ARCHIVE.part" "$ARCHIVE"
  GOT="$(sha256 "$ARCHIVE")"
  if [ "$GOT" != "$WANT" ]; then
    echo "archive sha256 MISMATCH: got $GOT, expected $WANT (the paper used dataset version 2)" >&2
    exit 1
  fi
  echo "archive sha256 OK ($WANT)"
fi

if [ "$EXTRACT" = 1 ]; then
  unzip -o -q "$ARCHIVE" GUIDE_Train.csv GUIDE_Test.csv -d "$DEST"
  ls -l "$DEST"/GUIDE_Train.csv "$DEST"/GUIDE_Test.csv
else
  unzip -l "$ARCHIVE" GUIDE_Train.csv GUIDE_Test.csv | sed -n '4,5p'
  echo "GUIDE ready: the pipeline reads these files from $ARCHIVE (no unpacking needed)"
fi
