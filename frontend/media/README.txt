hero.jpg is the landing-page image, loaded from /media/hero.jpg by the hero
frame in frontend/index.html.

Replace it with any square (1:1) image, ideally 1200x1200 or larger. If you use
a different filename or format, update the <img id="hero-image"> src in
frontend/index.html to match.

If the file is missing, the hero frame falls back to a dashed placeholder
instead of showing a broken image.

hero-image-prompt.txt holds the generation prompt used for the current image.
