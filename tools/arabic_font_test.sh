#!/usr/bin/env bash
# Renders the same Arabic samples with several fonts so harakat placement can be compared.
set -e
mkdir -p out/fonts
fc-list :lang=ar family | sort -u | head -40
for f in "Amiri" "Noto Naskh Arabic" "Scheherazade New"; do
  n=$(echo "$f" | tr ' ' '_')
  pango-view --no-display -q --output="out/fonts/$n.png" --font="$f 110" --dpi=72 --width=1800 --wrap=word \
    --align=center --rtl --background=white --foreground=black --margin=30 \
    --text="$f
الرَّحْمَٰنُ   الْقُدُّوسُ   الْمُهَيْمِنُ
اللَّهُمَّ إِنِّي أَسْأَلُكَ مِنْ فَضْلِكَ
رَبِّ زِدْنِي عِلْمًا" || echo "font $f failed"
done
ls -la out/fonts
