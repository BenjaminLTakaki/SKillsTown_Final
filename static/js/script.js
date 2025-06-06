function updateFileName() {
    const fileInput = document.getElementById('file');
    const fileNameContainer = document.getElementById('file-name');
    
    if (fileInput.files.length > 0) {
        const fileName = fileInput.files[0].name;
        fileNameContainer.innerHTML = `<div class="alert alert-success">
            <i class="fas fa-check-circle me-2"></i>Selected file: <strong>${fileName}</strong>
        </div>`;
        document.getElementById('submit-btn').removeAttribute('disabled');
    } else {
        fileNameContainer.innerHTML = '';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('dropzone');
    if (!dropzone) return;
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('bg-light');
    });
    
    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropzone.classList.remove('bg-light');
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('bg-light');
        
        const files = e.dataTransfer.files;
        const fileInput = document.getElementById('file');
        
        if (files.length > 0) {
            const fileName = files[0].name;
            const fileExt = fileName.split('.').pop().toLowerCase();
            
            if (['pdf', 'docx', 'txt'].includes(fileExt)) {
                fileInput.files = files;
                updateFileName();
            } else {
                document.getElementById('file-name').innerHTML = `<div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>Invalid file format. Please upload PDF, DOCX, or TXT files.
                </div>`;
            }
        }
    });
    
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(event) {
            const fileInput = document.getElementById('file');
            if (fileInput.files.length === 0) {
                event.preventDefault();
                document.getElementById('file-name').innerHTML = `<div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>Please select a file to upload.
                </div>`;
            } else {
                document.getElementById('submit-btn').innerHTML = `
                    <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    Analyzing CV...
                `;
                document.getElementById('submit-btn').disabled = true;
            }
        });
    }
    
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const skillBadges = document.querySelectorAll('.skills-badge');
    
    skillBadges.forEach((badge, index) => {
        setTimeout(() => {
            badge.style.opacity = '1';
            badge.style.transform = 'translateY(0)';
        }, 100 * index);
    });
});

function printResults() {
    window.print();
}

function copySkillsToClipboard() {
    const skillsContainer = document.querySelector('.skills-container');
    if (!skillsContainer) return;
    
    const skills = Array.from(skillsContainer.querySelectorAll('.skills-badge'))
        .map(badge => badge.textContent.trim())
        .join(', ');
    
    if (skills) {
        navigator.clipboard.writeText(skills).then(() => {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-success mt-3';
            alertDiv.innerHTML = '<i class="fas fa-check-circle me-2"></i>Skills copied to clipboard!';
            
            skillsContainer.parentNode.insertBefore(alertDiv, skillsContainer.nextSibling);
            
            setTimeout(() => {
                alertDiv.remove();
            }, 3000);
        });
    }
}