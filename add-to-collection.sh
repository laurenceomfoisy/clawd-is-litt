#!/bin/bash

API_KEY=$(jq -r .api_key ~/.openclaw/workspace/.zotero-config.json)
USER_ID=$(jq -r .user_id ~/.openclaw/workspace/.zotero-config.json)
COLLECTION_KEY="8SUXVGWQ"

# Item keys from all searches
ITEM_KEYS="ATHF8ZQK 4AQ22K6C SXK3SQHA 48QUNEQF 5BPCV4CZ MBMQAZJZ 386CNBJS K5NJM8TG ASQF4WB4 R8MMMWVU IM8DZNWN CDSV4DU2 66DUKNZR N9PXP9NU NG9BFH8K Z5BT9Q4I 3TGZE5SC 6ERDDIW8 8XWQB7MX VH6FKQBB NFIB5SE6 BAM3F5P2 4U4MEJPB JR58RFE2 67AW3FMB W7HKISC4 EKDC4JMT K9G4EPSI 5IJ2KV74 VFAXMPCQ 6NNXD639 Q74RIF42 X5BP7F3M 8ZDU64DQ B5W9QSH2 DWIPAFB6 FWCFQ859 44DQR27T FKWJ6HMT 84KJ28AI B7A4UX8Z SBBEX65I WW25QP84 X9ZEBQC4 XCGIXZ8H 3HAPGQ59 52JUPFZB CFSX3KQR 9USSJ8WB 5C4I8T6B APN9M7RI 4NUMWMPA 5ASRID64 E3X7V5W3 EJU7MNE5 575RSZPZ 75I3TTC9 FTDEM6RE EHJ6RBEM E8BBENDQ DA5BS7Z7 4CBXKESM CDVT3TWR FHBCSSZ2 29F2CW8J"

count=0
for key in $ITEM_KEYS; do
    # Get current item
    item=$(curl -s "https://api.zotero.org/users/${USER_ID}/items/${key}" \
        -H "Zotero-API-Key: ${API_KEY}")
    
    # Extract version
    version=$(echo "$item" | jq -r '.version')
    
    # Add collection to item
    updated=$(echo "$item" | jq ".data.collections += [\"${COLLECTION_KEY}\"]")
    
    # Update item
    curl -s -X PATCH "https://api.zotero.org/users/${USER_ID}/items/${key}" \
        -H "Zotero-API-Key: ${API_KEY}" \
        -H "Content-Type: application/json" \
        -H "If-Unmodified-Since-Version: ${version}" \
        -d "$updated" > /dev/null
    
    count=$((count + 1))
    echo -ne "\rAdded $count/65 papers to collection..."
done

echo -e "\n✅ All 65 papers added to collection 'IA et Communication Politique - Chapitre de Livre'"
