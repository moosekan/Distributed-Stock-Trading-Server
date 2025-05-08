FROM ubuntu:noble
#FROM ubuntu/python:3.12-24.04_stable

ENV VERSION=1.2

# set environment variables for tzdata
ARG TZ=America/New_York
ENV TZ=${TZ}

# include manual pages and documentation
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update &&\
 apt-get -y install unminimize &&\
 yes | unminimize

# install GCC-related packages
RUN apt-get -y install\
 binutils-doc\
 cpp-doc\
 gcc-doc\
 g++\
 g++-multilib\
 gdb\
 gdb-doc\
 glibc-doc\
 libblas-dev\
 liblapack-dev\
 liblapack-doc\
 libstdc++-13-doc\
 make\
 make-doc

# install clang-related packages
RUN apt-get -y install\
 clang\
 clang-18-doc\
 lldb\
 clang-format

# install qemu for WeensyOS (sadly, this pulls in a lot of crap)
RUN apt-get -y install\
 qemu-system-x86\
 qemu-user

# install programs used for system exploration
RUN apt-get -y install\
 blktrace\
 linux-tools-generic\
 strace\
 tcpdump

# install interactive programs (emacs, vim, nano, man, sudo, etc.)
RUN apt-get -y install\
 bc\
 curl\
 dc\
 emacs-nox\
 git\
 git-doc\
 man\
 micro\
 nano\
 psmisc\
 sudo\
 vim\
 wget

# install python and pip
RUN apt-get -y install\
 python3.12\
 python3.12-dev\
 python3.12-venv\
 python3-pip\
 python-is-python3\
 libjson-c-dev\
 libfuse-dev\
 fzf\
 openssh-server

# install java
RUN apt-get -y install\
 openjdk-11-jdk\
 openjdk-11-doc\
 openjdk-11-jre-headless\
 maven

# set up rsync, rpcbind
RUN apt-get -y install\
 rsync\
 rpcbind


#install python packages listed in requirements
#COPY requirements.txt /requirements.txt
# RUN pip3 install -r /requirements.txt
# set up pyro, grpc
#RUN apt-get -y install\
# python3-Pyro5\
# python3-grpcio\
# python3-grpcio-tools

# install rust
RUN RUSTUP_HOME=/opt/rust CARGO_HOME=/opt/rust \
  bash -c "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sudo -E sh -s -- -y"

# set up libraries
RUN apt-get -y install\
 libreadline-dev\
 locales\
 wamerican

# install programs used for networking
RUN apt-get -y install\
 dnsutils\
 inetutils-ping\
 iproute2\
 net-tools\
 netcat-openbsd\
 telnet\
 time\
 traceroute

# set up default locale
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8

# remove unneeded .deb files
RUN rm -r /var/lib/apt/lists/*

# set up passwordless sudo for user cs677-user
ARG UID=1001
RUN userdel -r ubuntu
RUN addgroup --gid "${UID}" cs677-user
RUN useradd -m -s /bin/bash -u "${UID}" -g "${UID}" cs677-user &&\
 echo "cs677-user ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/cs677-init

# create binary reporting version of dockerfile
RUN (echo '#\!/bin/sh'; echo 'echo 19') > /usr/bin/cs677-docker-version; chmod ugo+rx,u+w,go-w /usr/bin/cs677-docker-version

# git build arguments
ARG USER=cs677\ user
ARG EMAIL=nobody@example.com

# configure your environment
USER cs677-user
RUN git config --global user.name "${USER}" &&\
 git config --global user.email "${EMAIL}" &&\
 git config --global safe.directory "*" &&\
 (echo "(custom-set-variables"; echo " '(c-basic-offset 4)"; echo " '(indent-tabs-mode nil))") > ~/.emacs &&\
 (echo "set expandtab"; echo "set shiftwidth=4"; echo "set softtabstop=4") > ~/.vimrc &&\
 cat /dev/null > ~/.bash_profile &&\
 echo "# 2022: avoid a Docker bug with user mapping by listing working directory" >> ~/.bash_profile &&\
 echo "ls -al > /dev/null" >> ~/.bash_profile &&\
 echo "for i in \`mount | grep /home/cs677-user | sed 's/^.*\\(\\/home[^ ]*\\).*/\\\\1/'\`; do ls -al \$i > /dev/null; done" >> ~/.bash_profile &&\
 echo "# make ssh-auth.sock user-readable" >> ~/.bash_profile &&\
 (echo "if test -e /run/host-services/ssh-auth.sock; then"; echo "  sudo chown cs677-user:cs677-user /run/host-services/ssh-auth.sock"; echo "fi") >> ~/.bash_profile &&\
 echo ". ~/.bashrc" >> ~/.bash_profile &&\
 echo "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64" >> ~/.bash_profile &&\
 echo "export PATH=$PATH:$JAVA_HOME/bin">>~/.bash_profile &&\
 rm -f ~/.bash_logout &&\
 echo "add-auto-load-safe-path ~" > ~/.gdbinit

WORKDIR /home/cs677-user
CMD ["/bin/bash", "-l"]

# Initial version of this Dockerfile by Todd Morrill, CS 61 DCE student
# Used with permission from Harvard cs61
