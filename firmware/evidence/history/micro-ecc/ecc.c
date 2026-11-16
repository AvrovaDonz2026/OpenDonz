#include <stdint.h>
#include <stddef.h>
#include "uECC.h"
#include "ecc.h"
#include "random.h"
static int entropy(uint8_t *p,unsigned n) { uint8_t i=0; return random_gen(&i,p,n)==0; }
uint8_t *ecc_compute_public_p256r1(const uint8_t *k,uint8_t *p) { return uECC_compute_public_key(k,p,uECC_secp256r1()) ? 0 : p; }
int ecdsa_sign_p256r1(const uint8_t *h,uint8_t *s,const uint8_t *k) { uECC_set_rng(entropy); return uECC_sign(k,h,32,s,uECC_secp256r1()) ? 0 : -1; }
