#!/bin/bash
# This is Doorlock API stub
set -e
source ldap.cfg

if [ -z "$3" ]
then
    echo USAGE: `basename $0` LOCK_ID CARD_ID CARD_DATA
    exit 1
fi

LOCK_ID=$1              # 1st part of FLAG_ID (got on register)
CARD_ID=$2              # 2nd part of FLAG_ID (generated at checker)
CARD_DATA=$3            # FLAG

FOUND=`ldapsearch -h $LDAP_HOST -D $LDAP_USER -w $LDAP_PASS -b $LDAP_ROOT -LLL lockId=$LOCK_ID | grep cn: | wc -l`
if [ $FOUND -eq 0 ]
then
  echo LOCK NOT FOUND
  exit 0
fi

cat << EOF | ldapadd -h $LDAP_HOST -D $LDAP_USER -w $LDAP_PASS
dn: cn=$CARD_ID,cn=$LOCK_ID,cn=locks,$LDAP_ROOT
objectClass: top
objectClass: device
objectClass: cardObject
cardId:      $CARD_ID
cardData:    $CARD_DATA
EOF

echo "Added card (CN=$CARD_ID) to lock $LOCK_ID"
