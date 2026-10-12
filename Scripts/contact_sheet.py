"""Tile a capture folder's frame-XX.png files into one labelled contact sheet (review aid only)."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder')
    ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--width', type=int, default=480)
    args = ap.parse_args()
    folder = Path(args.folder)
    receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    frames = sorted(folder.glob('frame-*.png'))
    tiles = []
    for i, path in enumerate(frames):
        im = Image.open(path).convert('RGB')
        im = im.resize((args.width, int(im.height * args.width / im.width)))
        t = receipt['frames'][i]['request_elapsed_s'] if i < len(receipt['frames']) else 0
        ImageDraw.Draw(im).text((8, 8), '%02d  +%.1fs' % (i, t), fill=(255, 255, 0))
        tiles.append(im)
    rows = (len(tiles) + args.cols - 1) // args.cols
    sheet = Image.new('RGB', (args.cols * args.width, rows * tiles[0].height))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % args.cols) * args.width, (i // args.cols) * im.height))
    out = folder / 'contact-sheet.png'
    sheet.save(out)
    print(out)


if __name__ == '__main__':
    main()
