# Goals

- [x] one process per container
- [X] Starting the bare docker file will give you a basic zope / zms
- [x] everything as similar to our server deployment as possible to allow easy migration
- [x] modern os and python
- [x] simple to use and develop in vscode -> .devcontainer! FH has different solution
- [x] all mutable data in mounted volumes
- [x] Allow working on zms inside the container
- [x] example systemd files to run everything
  - [x] this should show how automated container updates are done!
- [ ] example nginx config so you get the same experience as on the server
- [ ] Full development experience with all dependennt services locally (mariadb, memcached, …)

# TODOs

- [x] Create basic Dockerfile for the project
- [x] specialize them for zeoserver and zope
- [x] create docker-compose file that runs each server separately
- [x] add devcontainer.json to develop and run everything from vscode
- [x] mount the zms source live into the container so working within it becomes possible
- [x] remove debug mode from zope Dockerfile
- [x] add script to run tests in docker
- [ ] add nginx, mariadb, memcached to docker-compose for a fully featured development environment, that can run production like configs
