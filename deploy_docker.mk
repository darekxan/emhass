image_ref := $(shell git describe --tags --exact-match 2> /dev/null || git rev-parse --verify --short HEAD)

registry := ghcr.io
owner := darekxan
image := emhass
full_image := ${registry}/${owner}/${image}

.PHONY: 

clean_deploy: deploy
	docker save -o ${image}_${image_ref}.tar ${full_image}:${image_ref}

deploy:
	docker build -t ${full_image}:${image_ref} --build-arg build_version=standalone -f Dockerfile .
