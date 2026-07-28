all: build

build:
	jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml

serve:
	python -m http.server 8000 --directory _build/html
