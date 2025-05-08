CS 677 Docker
============

NOTE: You do NOT need to rebuild the course docker for each lab. The docker image you built for lab0 should work for all labs and lablets (unless we release a new version of the docker image, in which case we will explicitly ask you to rebuild your docket image).

This folder and scripts are provided for convenience in case your docker image gets corrupted and needs to be rebuilt from scratch. 

The [Docker][] container-based virtualization service lets you run a
minimal CS 677 environment, including Linux, on a Mac OS X or Windows
computer, without the overhead of a full virtual machine like [VMware
Workstation][], [VMware Fusion][], or [VirtualBox][].

It should be possible to do *all* CS 677 labs and many lablets on CS 677 Docker.

Advantages of Docker:

* Docker can start and stop virtual machines incredibly quickly.
* Docker-based virtual machines are small and occupy little space on your machine.
* With Docker, you can easily *edit* your code in your home environment, but
  *compile and run* it on a Linux host.

Disadvantages of Docker:

* Docker does not offer a graphical environment. You will need to run all CS 677
  programs exclusively in the terminal.
* Docker technology is less user-friendly than virtual machines. You’ll have
  to type weird commands.
* You won’t get the fun, different feeling of a graphical Linux desktop.


## Creating CS 677 Docker

1.  Download and install [Docker][].

2.  Clone the github onto your computer.

3.  Change into the `docker` subdirectory.

4.  Run this command. It will take a while—up to ten minutes.

    ```shellsession
    $ ./cs677-build-docker
    ```

    The command starts up a virtual Linux-based computer running inside your
    computer. It then installs a bunch of software useful for CS 677 on that
    environment, then takes a snapshot of the running environment. (The
    snapshot has a name, such as `cs677:latest` or `cs677:arm64`.) Once the
    snapshot is created, it’ll take just a second or so for Docker to restart
    it.

We may need to change the Docker image during the term. If we do, you’ll
update your repository to get the latest Dockerfile, then re-run the
`./cs677-build-docker` command from Step 4. However, later runs should be
faster since they’ll take advantage of your previous work.

> `./cs677-build-docker` is a wrapper around `docker build`. On x86-64 hosts, it runs
> `docker build -t cs677:latest -f Dockerfile --platform linux/amd64 .`
{.note}

## Running CS 677 Docker by script

Our lab and lablet repositories contain
a `cs677-run-docker` script that provides good arguments and boots Docker into
a view of the current directory. We will update this script throughout the
term.

For example, here’s an example of running CS 677 Docker on a Mac OS X host. At
first, `uname` (a program that prints the name of the currently running
operating system) reports `Darwin`. But after `./cs677-run-docker` connects the
terminal to a Linux virtual machine, `uname` reports `Linux`. At the end of
the example, `exit` quits the Docker environment and returns the terminal to
Mac OS X.

```shellsession
$ cd ~/cs677-lab0
$ uname
Darwin
$ ./cs677-run-docker
cs677-user@a47f05ea5085:~/cs677-lab0$ uname
Linux
cs677-user@a47f05ea5085:~/cs677-lab0$ uname -a
Linux a47f05ea5085 5.10.47-linuxkit #1 SMP PREEMPT Sat Jul 3 21:50:16 UTC 2021 x86_64 x86_64 x86_64 GNU/Linux
cs677-user@a47f05ea5085:~/cs677-lectures$ ls
cs677-run-docker  docker  README.md
cs677-user@a47f05ea5085:~/cs677-lectures$ exit
exit
$ 
```

A prompt like `cs677-user@a47f05ea5085:~$` means that your terminal is
connected to the VM. (The `a47f05ea5085` part is a unique identifier for this
running VM.) You can execute any Linux commands you want. To escape from the
VM, type Control-D or run the `exit` command.

The script assumes your Docker container is named `cs677:latest` or `cs677:arm64`.


### Running CS 677 Docker by hand

If you don’t want to use the script, use a command like the following.

```shellsession
$ docker run -it --platform linux/amd64 --rm -v ~/cs677-lab0:/home/cs677-user/cs677-lab0 cs677:latest
```

Explanation:

* `docker run` tells Docker to start a new virtual machine.
* `-it` says Docker should run interactively (`-i`) using a terminal (`-t`).
* `--platform linux/amd64` says Docker should emulate an x86-64-based machine.
  It’s necessary to specify this if you have (for example) an Apple M1-based
  laptop.
* `--rm` says Docker should remove the virtual machine when it is done.
* `-v LOCALDIR:LINUXDUR` says Docker should share a directory between your
  host and the Docker virtual machine. Here, I’ve asked for the host’s
  `~/cs677-lab0` directory to be mapped inside the virtual machine onto the
  `/home/cs677-user/cs677-lab0` directory, which is the virtual machine
  user’s `~/cs677-lab0` directory.
* `cs677:latest` names the Docker image to run (namely, the one you built).

Here’s an example session:

```shellsession
$ docker run -it --platform linux/amd64 --rm -v ~/cs677-lab0:/home/cs677-user/cs677-lab0 cs677:latest
cs677-user@a15e6c4c8dbe:~$ ls
cs677-lab0
cs677-user@a15e6c4c8dbe:~$ echo "Hello, world"
Hello, world
cs677-user@a15e6c4c8dbe:~$ cs677-docker-version
16
cs677-user@a15e6c4c8dbe:~$ exit
exit
$ 
```

[Docker]: https://docker.com/
[VMware Workstation]: https://www.vmware.com/products/workstation-player.html
[VMware Fusion]: https://www.vmware.com/products/fusion.html
[VirtualBox]: https://www.virtualbox.org/

## Acknowledgements

This setup is a modified version of the setup used by
[Harvard's CS61](https://cs61.seas.harvard.edu/site/2021/) and reused
with permission.
