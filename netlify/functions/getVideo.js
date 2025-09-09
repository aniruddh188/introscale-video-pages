const fs = require('fs').promises;
const path = require('path');

exports.handler = async (event) => {
    try {
        const videoId = event.path.split('/').pop();

        const dataPath = path.resolve(__dirname, './videos.json');
        const templatePath = path.resolve(__dirname, '../../template.html');

        const videoData = JSON.parse(await fs.readFile(dataPath, 'utf-8'));
        let htmlTemplate = await fs.readFile(templatePath, 'utf-8');

        const prospectInfo = videoData[videoId];

        if (!prospectInfo) {
            return {
                statusCode: 404,
                body: '<h1>Video not found</h1><p>The requested video does not exist.</p>',
            };
        }

        htmlTemplate = htmlTemplate.replace(/{{PROSPECT_NAME}}/g, prospectInfo.prospectName);
        htmlTemplate = htmlTemplate.replace('{{FINAL_VIDEO_URL}}', prospectInfo.finalVideoUrl);
        // --- THIS IS THE NEW LINE ---
        htmlTemplate = htmlTemplate.replace('{{WEBSITE_URL}}', prospectInfo.websiteUrl || ''); 
        
        return {
            statusCode: 200,
            body: htmlTemplate,
            headers: { 'Content-Type': 'text/html' },
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: `<h1>Error</h1><p>An error occurred: ${error.message}</p>`,
        };
    }
};
