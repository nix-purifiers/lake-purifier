#include <lean/lean.h>
extern lean_object *initialize_nativeProjectionProof_Native(uint8_t builtin);
LEAN_EXPORT int projection_initialize(void) {
 lean_object *result = initialize_nativeProjectionProof_Native(1);
 if (lean_io_result_is_error(result)) { lean_dec(result); return 0; }
 lean_dec(result);
 lean_io_mark_end_initialization();
 return 1;
}
