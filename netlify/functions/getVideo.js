const fs = require('fs').promises;
const path = require('path');

exports.handler = async (event) => {
    try {
        // Extract the unique video ID from the URL path (e.g., /rEda3a18293)
        const videoId = event.path.split('/').pop();

        // Define paths to the data and template files
        const dataPath = path.resolve(__dirname, '../../videos.json');
        const templatePath = path.resolve(__dirname, '../../template.html');

        // Read the files from the deployed site
        const videoData = JSON.parse(await fs.readFile(dataPath, 'utf-8'));
        let htmlTemplate = await fs.readFile(templatePath, 'utf-8');

        // Find the specific prospect's data using the ID from the URL
        const prospectInfo = videoData[videoId];

        // If no data is found for that ID, show a "not found" page
        if (!prospectInfo) {
            return {
                statusCode: 404,
                body: '<h1>Video not found</h1><p>The requested video does not exist.</p>',
            };
        }

        // Replace all the placeholders in the template with the prospect's data
        htmlTemplate = htmlTemplate.replace(/{{PROSPECT_NAME}}/g, prospectInfo.prospectName);
        htmlTemplate = htmlTemplate.replace('{{SCREEN_VIDEO_URL}}', prospectInfo.screenVideoUrl);
        htmlTemplate = htmlTemplate.replace('{{FACE_VIDEO_URL}}', prospectInfo.faceVideoUrl);
        htmlTemplate = htmlTemplate.replace('{{THUMBNAIL_URL}}', prospectInfo.thumbnailUrl);
        
        // Send the final, personalized HTML page to the user's browser
        return {
            statusCode: 200,
            body: htmlTemplate,
            headers: { 'Content-Type': 'text/html' },
        };
    } catch (error) {
        // If anything goes wrong, show a generic error page
        return {
            statusCode: 500,
            body: `<h1>Error</h1><p>An error occurred: ${error.message}</p>`,
        };
    }
};