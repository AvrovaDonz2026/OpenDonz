#ifndef assert
void crypto_abort(int);
#define assert(x) ((x) ? (void)0 : crypto_abort(1))
#endif
