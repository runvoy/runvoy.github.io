# Runvoy docs site generator

We're going to use this repo to generate the docs site for the Runvoy project.

It's going to be a python script (we'll use uv to manage the dependencies).

We'll use the `mkdocs` library to generate the site.

We'll use the `mkdocs-material` theme to style the site.

The script will run as a github action on the `main` branch, flow will be:

1. use GitHub APIs to find all the markdown files in <https://github.com/runvoy/runvoy/tree/main/docs>
2. generate the site using the `mkdocs` library
   - use README.md as the index page
   - replace all the links to the markdown files with the generated site links (probably there's an mkdoc plugin to do it natively, probably is as easy as stripping `docs/` from the links)
3. upload the generated site with artifacts action
4. push the generated site with the official GitHub pages action
