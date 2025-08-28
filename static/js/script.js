// Toggle meal attendance
document.addEventListener('DOMContentLoaded', function() {
    // Meal attendance checkboxes
    const mealCheckboxes = document.querySelectorAll('.meal-checkbox');
    mealCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const studentId = this.dataset.studentId;
            const mealType = this.dataset.mealType;
            const dateInput = document.getElementById('attendance-date');
            const date = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];
            const action = this.checked ? 'mark' : 'unmark';
            
            // Create URL-encoded form data
            const formData = new URLSearchParams();
            formData.append('student_id', studentId);
            formData.append('meal_type', mealType);
            formData.append('action', action);
            formData.append('date', date);
            
            fetch('/admin/attendance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData.toString()
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (!data.success) {
                    console.error('Server error:', data.error);
                    alert('Error updating attendance: ' + (data.error || 'Unknown error'));
                    this.checked = !this.checked;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error updating attendance. Please check console for details.');
                this.checked = !this.checked;
            });
        });
    });
    
    // Date picker for attendance
    const attendanceDate = document.getElementById('attendance-date');
    if (attendanceDate) {
        attendanceDate.addEventListener('change', function() {
            window.location.href = `/admin/attendance?date=${this.value}`;
        });
    }
    
    // Report date filters
    const reportStartDate = document.getElementById('report-start-date');
    const reportEndDate = document.getElementById('report-end-date');
    const reportType = document.getElementById('report-type');
    const filterBtn = document.getElementById('filter-btn');
    const downloadBtn = document.getElementById('download-btn');

    if (reportStartDate && reportEndDate && reportType) {
        const updateReport = function() {
            window.location.href = `/admin/reports?type=${reportType.value}&start_date=${reportStartDate.value}&end_date=${reportEndDate.value}`;
        };

        const updateDownloadLink = function() {
            const downloadUrl = `/admin/reports/export?type=${reportType.value}&start_date=${reportStartDate.value}&end_date=${reportEndDate.value}`;
            downloadBtn.setAttribute('href', downloadUrl);
        };
        
        filterBtn.addEventListener('click', updateReport);
        reportType.addEventListener('change', updateDownloadLink);
        reportStartDate.addEventListener('change', updateDownloadLink);
        reportEndDate.addEventListener('change', updateDownloadLink);

        // Initial update of the download link
        updateDownloadLink();
    }
    
    
    // Debug: Log all checkboxes found
    console.log('Meal checkboxes found:', mealCheckboxes.length);
});