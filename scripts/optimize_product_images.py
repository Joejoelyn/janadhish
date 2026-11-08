"""Create smaller storefront copies without changing the source photos."""

from pathlib import Path

from PIL import Image, ImageOps


SOURCE_ROOT = Path(__file__).resolve().parents[1] / 'frontend' / 'Images' / 'products'
MAX_SIZE = (1800, 1800)


def main() -> None:
    originals = 0
    optimized = 0
    count = 0
    for source in SOURCE_ROOT.rglob('*'):
        if not source.is_file() or source.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
            continue
        target = source.with_suffix('.webp')
        originals += source.stat().st_size
        if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
                if image.mode not in {'RGB', 'RGBA'}:
                    image = image.convert('RGB')
                image.save(
                    target, 'WEBP', quality=84, method=6,
                    icc_profile=image.info.get('icc_profile'),
                )
            count += 1
        optimized += target.stat().st_size
    print(f'{count} images generated; {originals / 1048576:.1f} MB source, {optimized / 1048576:.1f} MB storefront')


if __name__ == '__main__':
    main()
