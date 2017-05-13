## Doorlock service writeup

> Author: Dimmoborgir, Hackerdom team

Service is a controller of "smart" door locks. It processes requests using
COAP protocol at port 5683/udp. COAP protocol is like HTTP, but is binary and 
uses UDP :) Service allows register new locks and add access cards to them.
Service generates new random lock id on each lock registration.
To add access card you should specify lock Id and card's Tag.
Card's tags contain flags. Data is saved in LDAP database.

There is a handy nodejs client for COAP protocol:
```
$ sudo apt install nodejs npm
$ sudo npm install coap-cli -g
$ coap get "coap://10.60.123.2/get_card?lock=QWERTY&card=123456"
(2.05)	EMPTY
```

## First look

There is only one file (docker-compose.yml) in service catalog (/home/ctf/doorlock).
There are neither sources, nor executables.

Let's look inside running docker-container:

```
root@phdays2017:~# docker exec -i -u root -t doorlock /bin/bash

root@7119bb47044d:/app# ps axf
  PID TTY      STAT   TIME COMMAND
   42 ?        Ss     0:00 /bin/bash
   72 ?        R+     0:00  \_ ps axf
    1 ?        Ss     0:00 /bin/sh -c /app/docker-wrapper.sh
    5 ?        S      0:00 /bin/bash /app/docker-wrapper.sh
    6 ?        Sl     0:00  \_ /usr/sbin/slapd -h ldap://127.0.0.1:389/ ...
   32 ?        S      0:00  \_ /app/doorlock-server
```
We see two main processes: slapd (LDAP server) and doorlock-server (service itself).

There are sources in the /app directory (doorlock-server.cpp):
```
root@7119bb47044d:/app# ls
Makefile        docker-wrapper.sh  doorlock-server.cpp  doorlock-server.o  ldap-dpkg-reconfigure.sh 
ldap.cfg        add-locks.ldif     doorlock-server      doorlock-server.d  include
ldap-init.sh    libs
```
Let's copy /app directory from docker-container to vulnimage for further research:
```
root@phdays2017:~# docker cp doorlock:/app app
```
## Vulnerability 1 (simple)

Let's look at doorlock-server.cpp. init_resources function registers handlers for 
COAP-requests. Service responds to the following requests:

```
GET  /              without arguments
```
Always responds with the same response. Does not talk to LDAP. Not interesting.

```
POST /register_lock  with arguments: model, floor, room
```
Creates new object (lockObject) in LDAP with the following structure:
```
    objectClass: top
    objectClass: device
    objectClass: lockObject
    lockModel:   [request argument 'model']
    lockFloor:   [request argument 'floor']
    lockRoom:    [request argument 'room']
    timestamp:   199412161032Z
```
Object is created with DN: cn=[lock_id],cn=locks,dc=iot,dc=phdays,dc=com
(DN in LDAP uniquely describes an object in object tree)
[lock_id] - is random string with length 9, generated by service
```
POST /add_card   with arguments: lock, card, tag
```
Creates new object (cardObject) in LDAP with the following structure:
```
    objectClass: top
    objectClass: device
    objectClass: cardObject
    lockId:      [request argument 'lock']
    card:        [request argument 'card']
    cardTag:     [request argument 'tag']
    cardOwner:   John Doe
    timestamp:   199412161032Z
```
Object is created with DN: cn=[card],cn=[lock],cn=locks,dc=iot,dc=phdays,dc=com
```
GET  /get_card   with arguments: lock, card
```
Makes read query to LDAP. Query is built as: `sprintf( query, "(&(cn=%s)(lockId=%s))", card, lock )`

Syntax `(&(FOO)(BAR))` means fulfillment of both conditions: FOO and BAR.

After query was built, it is pre-processed by two functions:
1. ldap_sanitize()
  * replaces "dangerous" symbols (*,~,\\,|) to _ 
  * puts zero symbol after last ')' symbol
2. ldap_validate() - checks that there are exactly 3 ')' and 3 '(' symbols

First vulerability is here: if pass card argument as 
`N)(%26))`, it will create query `(&(cn=X)(&))`.
`(&)` is always true. That is, you only need to know card_id, to get access to its private tag (flag).

Two kinds of card is are being registered in the service:
1. secur???????? (? - means any char) - amount 80% of all flags
2. N (N - is number from 1 to ..., incrementing by 1) - amount 80% of all flags

This vulnerability allows by issuing `/get_card` requests with card arguments:  
"1)(%26))", "2)(%26))", "3)(%26))", "4)(%26))", ... obtain 20% of flags.
lock parameter can be arbitrary - it will be ignored.

## Vulnerability 2 (hard)

The service uses libcoap C library which implements COAP protocol. Its binary is located in directory 'libs'.
Let's first look at strings in this binary:

```
root@phdays2017:~# strings libcoap-1.a
```

We can see suspicious strings which make us think about backdoor:

```
commit 012a1a1482e30de1dda7d142de27de91d23c4501Merge: b425b15 f122811
Author: Krait <krait@dqteam.org>
Date:   Wed May 3 14:45:52 2017 +0500
Merge branch 'backdoor'
```
```
/home/dima/git/phdctf-2017/services/doorlock/backdoor/libcoap
```
In one of suspicious strings there is commit hash (b425b15).
After googling it, we can easily find repo https://github.com/obgm/libcoap

Let's clone it, checkout to commit b425b15 and make binary:

```
root@phdays2017:~# git clone https://github.com/obgm/libcoap.git
root@phdays2017:~# cd libcoap/
root@phdays2017:~/libcoap# git checkout b425b15
root@phdays2017:~/libcoap# apt-get -y install libtool autoconf pkgconf
root@phdays2017:~/libcoap# ./autogen.sh && ./configure --disable-examples && make
```
Compare `libcoap-1.a` files: just built from sources and from service directory.
We'll use command: `objdump -M intel -d libcoap-1.a`
Let's wrap it in a simple script to compare functions (./objd-lines.pl)

```
#!/usr/bin/perl
# objd-lines.pl

@ARGV==2 or die "Args: ORIG PATCHED\n";

sub counts {
	my $fname = shift;
	my %R = ();
	my ($name, $lines) = ('', 0);
	for (`objdump -M intel -d $fname`) {
		if (m|^\S+ <(\S+)>:|) {
			$R{$name} = $lines if $name;
			($name, $lines) = ($1, 0);
		}
		$lines++ if m|^\s+\S+:|;
	}
	$R{$name} = $lines if $name;
	return %R;
}

my %O  = counts($ARGV[0]);
my %M = counts($ARGV[1]);

for (sort {$a->[1] <=> $b->[1]} map { [$_, $M{$_}-$O{$_} ] } keys %M) {
	my $k = $_->[0];
	my $delta = $_->[1];
	next if $delta == 0 || $M{$k} == 0 || $O{$k} == 0;
	printf "%30s   orig:%4d   mod:%4d   diff:%2d\n", $k, $O{$k}, $M{$k}, $M{$k} - $O{$k};
}
```

```
# ./objd-lines.pl .libs/libcoap-1.a ../app/libs/libcoap-1.a 
                  write_option   orig: 140   mod: 134   diff:-6
               coap_retransmit   orig:  82   mod:  79   diff:-3
    print_readable.constprop.1   orig:  87   mod:  85   diff:-2
          coap_write_block_opt   orig: 125   mod: 123   diff:-2
                   no_response   orig:  70   mod:  69   diff:-1
          coap_print_wellknown   orig: 256   mod: 257   diff: 1
                 coap_add_data   orig:  68   mod:  69   diff: 1
                coap_add_block   orig:  19   mod:  21   diff: 2
               coap_print_link   orig: 208   mod: 211   diff: 3
                coap_pdu_parse   orig: 178   mod: 181   diff: 3
         coap_add_option_later   orig:  63   mod:  67   diff: 4
               coap_add_option   orig:  55   mod:  60   diff: 5
       coap_wellknown_response   orig: 292   mod: 299   diff: 7
                  hash_segment   orig:   4   mod:  11   diff: 7
             coap_network_send   orig: 130   mod: 170   diff:40
``` 

`coap_network_send` function was increased more than others - diff is 40 opcodes.
Look at the disassembly.

Two blocks were added.

In the first block whole sending buffer is being copied to a separate buffer.

In the second block there is check for signature 'LITLGIRL' inside sending packet:
```
 496:	48 be 4c 49 54 4c 47 	movabs rsi,0x4c5249474c54494c
```
```
# python3 -c "print(bytearray.fromhex('4c5249474c54494c'))"
bytearray(b'LRIGLTIL')
```
If the signature was found, that separate buffer (stored before) is sent as a reply.

Backdoor can be used in the following way:
* Put a flag (card's tag), to the service wich starts with 'LITLGIRL', e.g.: `LITLGIRLJTINJEKCADGGJBWDEIOVCMX=`
* Get that flag. We'll get some other (last) flag in response (not ours).

Exploits are in [sploits](../sploits/doorlock) directory.
