type Field = HTMLInputElement | HTMLTextAreaElement;

export function formIssue(form: HTMLFormElement): string | null {
  const checkedRadioGroups = new Set<string>();
  for (const element of Array.from(form.elements)) {
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) continue;
    if (element instanceof HTMLInputElement && element.type === 'radio') {
      if (!element.required || checkedRadioGroups.has(element.name)) continue;
      checkedRadioGroups.add(element.name);
      const options = Array.from(form.elements).filter((field): field is HTMLInputElement =>
        field instanceof HTMLInputElement && field.type === 'radio' && field.name === element.name);
      if (options.some(option => option.checked)) {
        options.forEach(option => option.removeAttribute('aria-invalid'));
        continue;
      }
      options.forEach(option => {
        option.setAttribute('aria-invalid', 'true');
        option.addEventListener('change', () => options.forEach(item => item.removeAttribute('aria-invalid')), { once: true });
      });
      element.focus();
      const legend = element.closest('fieldset')?.querySelector('legend')?.textContent?.replace(/^\d+\.\s*/, '').trim();
      return `Choose ${(legend || element.name.replaceAll('_', ' ')).toLowerCase()}.`;
    }
    if (element instanceof HTMLInputElement && element.type === 'checkbox') {
      if (element.required && !element.checked) {
        element.setAttribute('aria-invalid', 'true');
        element.addEventListener('change', () => element.removeAttribute('aria-invalid'), { once: true });
        element.focus();
        return 'Confirm the required review check before continuing.';
      }
      continue;
    }
    if (element instanceof HTMLInputElement && element.type === 'hidden') continue;
    const field: Field = element;
    const label = field.labels?.[0]?.textContent?.trim() || field.name.replaceAll('_', ' ');
    const blank = field.required && !field.value.trim();
    if (!blank && field.checkValidity()) { field.removeAttribute('aria-invalid'); continue; }
    field.setAttribute('aria-invalid', 'true');
    field.addEventListener('input', () => field.removeAttribute('aria-invalid'), { once: true });
    field.focus();
    if (blank) return `Enter ${label.toLowerCase()}.`;
    if (field.validity.typeMismatch) return `Enter a valid ${label.toLowerCase()}.`;
    if (field.validity.patternMismatch) return field.title || `Check ${label.toLowerCase()}.`;
    if (field.validity.tooShort) return `${label} is too short.`;
    if (field.validity.tooLong) return `${label} is too long.`;
    if (field.validity.rangeOverflow || field.validity.rangeUnderflow) return `Check the ${label.toLowerCase()} value.`;
    return `Check ${label.toLowerCase()}.`;
  }
  return null;
}
