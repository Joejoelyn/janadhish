const garmentOptions = [
  { id: 'saree', name: 'Saree' },
  { id: 'kurta', name: 'Kurta' },
  { id: 'anarkali', name: 'Anarkali' },
  { id: 'fusion-set', name: 'Fusion Set' },
  { id: 'gown', name: 'Gown' },
];

const measurementLabels = {
  saree: ['Waist', 'Hips', 'Shoulder to waist', 'Saree length', 'Pallu length'],
  kurta: ['Chest', 'Waist', 'Hips', 'Shoulder', 'Sleeve length', 'Kurta length'],
  anarkali: ['Bust', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Gown length'],
  'fusion-set': ['Bust', 'Waist', 'Hip', 'Shoulder', 'Trouser waist', 'Pant length'],
  gown: ['Bust', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Gown length'],
};

let currentStep = 1;
const totalSteps = 5;

function renderGarments() {
  const container = document.getElementById('garmentOptions');
  container.innerHTML = garmentOptions.map(option => `
    <label class="option-item" data-garment="${option.id}">
      <input type="radio" name="garment" value="${option.id}" hidden />
      ${option.name}
    </label>
  `).join('');

  document.querySelectorAll('[data-garment]').forEach((el) => {
    el.addEventListener('click', () => {
      document.querySelectorAll('[data-garment]').forEach(item => item.classList.remove('is-selected'));
      el.classList.add('is-selected');
      el.querySelector('input').checked = true;
      renderMeasurements();
    });
  });
}

async function renderFabricOptions() {
  const response = await fetch(`${API_BASE}/api/fabrics`);
  const fabrics = await response.json();
  const container = document.getElementById('fabricOptions');
  container.innerHTML = fabrics.map((fabric) => `
    <label class="option-item" data-fabric="${fabric.id}">
      <input type="radio" name="fabric" value="${fabric.name}" hidden />
      <img src="${fabric.image_url || '/assets/images/fabrics/cotton-silk.svg'}" alt="${fabric.name}" />
      <div><strong>${fabric.name}</strong><p>${fabric.description}</p></div>
    </label>
  `).join('');

  document.querySelectorAll('[data-fabric]').forEach((el) => {
    el.addEventListener('click', () => {
      document.querySelectorAll('[data-fabric]').forEach(item => item.classList.remove('is-selected'));
      el.classList.add('is-selected');
      el.querySelector('input').checked = true;
    });
  });
}

async function renderDesignOptions() {
  const response = await fetch(`${API_BASE}/api/designs`);
  const designs = await response.json();
  const container = document.getElementById('designOptions');
  container.innerHTML = designs.map((design) => `
    <label class="option-item" data-design="${design.id}">
      <input type="radio" name="design" value="${design.name}" hidden />
      <img src="${design.image_url || '/assets/images/designs/floral-chikankari.svg'}" alt="${design.name}" />
      <div><strong>${design.name}</strong><p>${design.description}</p></div>
    </label>
  `).join('');

  document.querySelectorAll('[data-design]').forEach((el) => {
    el.addEventListener('click', () => {
      document.querySelectorAll('[data-design]').forEach(item => item.classList.remove('is-selected'));
      el.classList.add('is-selected');
      el.querySelector('input').checked = true;
    });
  });
}

function renderMeasurements() {
  const garmentInput = document.querySelector('input[name="garment"]:checked');
  const selectedGarment = garmentInput ? garmentInput.value : 'saree';
  const labels = measurementLabels[selectedGarment] || measurementLabels.saree;
  const container = document.getElementById('measurementFields');
  container.innerHTML = labels.map((label, index) => {
    const fieldId = `measurement-${index + 1}`;
    return `
      <div class="form-row measurement-field">
        <label for="${fieldId}">${label}<span aria-hidden="true">*</span></label>
        <div class="measurement-input-wrap">
          <input id="${fieldId}" type="number" name="measurement" data-measurement-label="${label}" min="0.1" max="300" step="0.1" inputmode="decimal" placeholder="0.0" required />
          <span class="measurement-unit-suffix" aria-hidden="true"></span>
        </div>
      </div>
    `;
  }).join('');
  updateMeasurementUnitLabels();
}

function updateMeasurementUnitLabels() {
  const unit = document.getElementById('measurementUnit')?.value || 'inches';
  document.querySelectorAll('.measurement-unit-suffix').forEach((suffix) => {
    suffix.textContent = unit === 'cm' ? 'cm' : 'in';
  });
}

function updateStepDisplay() {
  const steps = document.querySelectorAll('.form-step');
  steps.forEach((step, index) => {
    const isActive = index + 1 === currentStep;
    step.classList.toggle('is-visible', isActive);
  });

  const stepBadges = document.querySelectorAll('#customStepList span');
  stepBadges.forEach((badge, index) => (
    badge.classList.toggle('is-active', index + 1 === currentStep)
  ));

  const prevButton = document.getElementById('prevStep');
  const nextButton = document.getElementById('nextStep');
  const submitButton = document.getElementById('submitCustomOrder');

  prevButton.disabled = currentStep === 1;
  nextButton.classList.toggle('hidden', currentStep === totalSteps);
  submitButton.classList.toggle('hidden', currentStep !== totalSteps);
}

function buildSummary() {
  const garment = document.querySelector('input[name="garment"]:checked')?.value || 'Not selected';
  const fabric = document.querySelector('input[name="fabric"]:checked')?.value || 'Not selected';
  const design = document.querySelector('input[name="design"]:checked')?.value || 'Not selected';
  const unit = document.getElementById('measurementUnit')?.value || 'inches';
  const unitLabel = unit === 'cm' ? 'cm' : 'in';
  const measurements = Array.from(document.querySelectorAll('input[name="measurement"]'))
    .map((input) => `${input.dataset.measurementLabel}: ${input.value || 'Not provided'} ${unitLabel}`);
  const preferences = document.getElementById('customPreferences').value || 'Not provided';
  const specialInstructions = document.getElementById('specialInstructions').value || 'No additional instructions';

  const summary = document.getElementById('customSummary');
  summary.replaceChildren();
  const summaryItems = [
    ['Garment', garment],
    ['Fabric', fabric],
    ['Design', design],
    ['Unit', unit === 'cm' ? 'Centimetres (cm)' : 'Inches (in)'],
    ['Measurements', measurements.join(' · ') || 'Not provided'],
    ['Style preferences', preferences],
    ['Special instructions', specialInstructions],
  ];
  summaryItems.forEach(([label, value]) => {
    const row = document.createElement('p');
    const heading = document.createElement('strong');
    heading.textContent = `${label}: `;
    row.append(heading, document.createTextNode(value));
    summary.append(row);
  });
}

function validateCurrentStep() {
  if (currentStep === 1 && !document.querySelector('input[name="garment"]:checked')) {
    alert('Please choose a garment type before continuing.');
    return false;
  }

  if (currentStep === 2 && !document.querySelector('input[name="fabric"]:checked')) {
    alert('Please select a fabric before continuing.');
    return false;
  }

  if (currentStep === 3 && !document.querySelector('input[name="design"]:checked')) {
    alert('Please choose a design before continuing.');
    return false;
  }

  if (currentStep === 4) {
    const measurementInputs = Array.from(document.querySelectorAll('input[name="measurement"]'));
    const incompleteInput = measurementInputs.find((input) => !input.value || !input.checkValidity());
    if (incompleteInput) {
      incompleteInput.reportValidity();
      return false;
    }
  }

  buildSummary();
  return true;
}

document.getElementById('nextStep').addEventListener('click', () => {
  if (!validateCurrentStep()) return;
  currentStep = Math.min(currentStep + 1, totalSteps);
  updateStepDisplay();
});

document.getElementById('prevStep').addEventListener('click', () => {
  currentStep = Math.max(currentStep - 1, 1);
  updateStepDisplay();
});

document.getElementById('measurementUnit').addEventListener('change', updateMeasurementUnitLabels);

document.getElementById('customMadeForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const status = document.getElementById('customRequestStatus');
  const submitButton = document.getElementById('submitCustomOrder');
  const measurementInputs = Array.from(document.querySelectorAll('input[name="measurement"]'));
  const incompleteInput = measurementInputs.find((input) => !input.value || !input.checkValidity());
  if (!incompleteInput) {
    buildSummary();
  } else {
    currentStep = 4;
    updateStepDisplay();
    incompleteInput.reportValidity();
    return;
  }

  status.textContent = '';
  submitButton.disabled = true;
  submitButton.textContent = 'Sending request…';

  const payload = {
    garment_category: document.querySelector('input[name="garment"]:checked')?.value,
    fabric_name: document.querySelector('input[name="fabric"]:checked')?.value,
    design_name: document.querySelector('input[name="design"]:checked')?.value,
    measurements: Object.fromEntries(measurementInputs.map((input) => [
      input.dataset.measurementLabel,
      Number(input.value),
    ])),
    preferences: {
      style: document.getElementById('customPreferences').value || '',
      measurement_unit: document.getElementById('measurementUnit').value,
    },
    special_instructions: document.getElementById('specialInstructions').value || '',
  };

  try {
    const response = await fetch(`${API_BASE}/api/customizations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Unable to save your measurement request right now.');
    }
    status.textContent = `Your measurement request #${data.id} has been received. Our team will review the details and contact you. No order or payment has been placed.`;
    submitButton.classList.add('hidden');
  } catch (error) {
    status.textContent = error.message || 'Unable to send your request. Please try again.';
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Send measurement request';
  }
});

window.addEventListener('DOMContentLoaded', async () => {
  renderGarments();
  await renderFabricOptions();
  await renderDesignOptions();
  renderMeasurements();
  updateStepDisplay();
});
