#include <stdint.h>
#include <stddef.h>
#include "ecc.h"
#include "random.h"
#include "mbedtls/ecp.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/memory_buffer_alloc.h"
#include "mbedtls/platform_util.h"
/* Bounded upstream allocator: single synchronous crypto operation at a time. */
static unsigned char arena[8192] __attribute__((aligned(8)));
static int entropy(void *ctx, unsigned char *p, size_t n) {
    uint8_t index = 0; (void)ctx;
    return random_gen(&index, p, n) == 0 ? 0 : MBEDTLS_ERR_ECP_RANDOM_FAILED;
}
void crypto_abort(int status) { (void)status; for (;;) {} }
static int load(mbedtls_ecp_group *g, mbedtls_mpi *d, const uint8_t *key) {
    int ret = mbedtls_ecp_group_load(g, MBEDTLS_ECP_DP_SECP256R1);
    if (!ret) ret = mbedtls_mpi_read_binary(d, key, 32);
    if (!ret) ret = mbedtls_ecp_check_privkey(g, d);
    return ret;
}
uint8_t *ecc_compute_public_p256r1(const uint8_t *key, uint8_t *out) {
    mbedtls_ecp_group g; mbedtls_ecp_point q; mbedtls_mpi d;
    unsigned char encoded[65]; size_t len = 0;
    mbedtls_memory_buffer_alloc_init(arena, sizeof(arena));
    mbedtls_ecp_group_init(&g); mbedtls_ecp_point_init(&q); mbedtls_mpi_init(&d);
    int ret = load(&g, &d, key);
    if (!ret) ret = mbedtls_ecp_mul(&g, &q, &d, &g.G, entropy, NULL);
    if (!ret) ret = mbedtls_ecp_point_write_binary(&g, &q, MBEDTLS_ECP_PF_UNCOMPRESSED, &len, encoded, sizeof(encoded));
    if (!ret && len != 65) ret = -1;
    if (!ret) for (unsigned i = 0; i < 64; ++i) out[i] = encoded[i+1];
    mbedtls_mpi_free(&d); mbedtls_ecp_point_free(&q); mbedtls_ecp_group_free(&g);
    mbedtls_memory_buffer_alloc_free(); mbedtls_platform_zeroize(arena, sizeof(arena));
    return ret ? out : NULL;
}
int ecdsa_sign_p256r1(const uint8_t *hash, uint8_t *out, const uint8_t *key) {
    mbedtls_ecp_group g; mbedtls_mpi d, r, s; unsigned char encoded[64];
    mbedtls_memory_buffer_alloc_init(arena, sizeof(arena));
    mbedtls_ecp_group_init(&g); mbedtls_mpi_init(&d); mbedtls_mpi_init(&r); mbedtls_mpi_init(&s);
    int ret = load(&g, &d, key);
    if (!ret) ret = mbedtls_ecdsa_sign(&g, &r, &s, &d, hash, 32, entropy, NULL);
    if (!ret) ret = mbedtls_mpi_write_binary(&r, encoded, 32);
    if (!ret) ret = mbedtls_mpi_write_binary(&s, encoded+32, 32);
    if (!ret) for (unsigned i = 0; i < 64; ++i) out[i] = encoded[i];
    mbedtls_mpi_free(&s); mbedtls_mpi_free(&r); mbedtls_mpi_free(&d); mbedtls_ecp_group_free(&g);
    mbedtls_memory_buffer_alloc_free(); mbedtls_platform_zeroize(arena, sizeof(arena));
    mbedtls_platform_zeroize(encoded, sizeof(encoded));
    return ret ? -1 : 0;
}
