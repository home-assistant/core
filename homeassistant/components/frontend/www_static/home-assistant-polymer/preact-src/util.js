export function validEntityId(entityId) {
  return /^(\w+)\.(\w+)$/.test(entityId);
}
