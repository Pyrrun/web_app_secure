echo "PL
aasdf
asdf
asdf
asdf
asdf
asdf
asdf
asdf  
"|openssl req -nodes -new -x509 -days 365 -keyout ca.key -out ca-crt.pem
echo "PL
aasdf
asdf
asdf
asdf
asdf
asdf
asdf
asdf      
"|openssl req -nodes -new -keyout server.key -out server.csr 
openssl x509 -req -days 365 -in server.csr -CA ca-crt.pem -CAkey ca.key -CAcreateserial -out server.crt
