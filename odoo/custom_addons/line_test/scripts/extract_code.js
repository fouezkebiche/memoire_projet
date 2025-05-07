const fs = require('fs');
const path = require('path');

// Go up one level to the main module directory
const sourceFolder = path.resolve(__dirname, '..');
const outputFile = path.join(__dirname, 'odoo_code_output.txt');
const extensions = ['.py', '.xml', '.csv']; // File types in your Odoo module

function concatenateFiles(folderPath, depth = 0) {
  const files = fs.readdirSync(folderPath);
  let fileContent = '';
  let folderContent = '';

  files.forEach(file => {
    const filePath = path.join(folderPath, file);
    const stats = fs.statSync(filePath);

    if (stats.isDirectory()) {
      const subContent = concatenateFiles(filePath, depth + 1);
      if (subContent && subContent.trim()) {
        folderContent += `\n\n\n\n\n\n\n\n// ${'  '.repeat(depth)}[Folder] ${file}\n${subContent}\n\n`;
      }
    } else {
      for (const ext of extensions) {
        if (file.endsWith(ext)) {
          const fileData = fs.readFileSync(filePath, 'utf-8');
          fileContent += `\n\n\n\n\n\n\n\n// ${filePath}\n${fileData}`;
          break;
        }
      }
    }
  });

  return folderContent + fileContent;
}

// Start with a clean output file
fs.writeFileSync(outputFile, '', 'utf-8');
const allContent = concatenateFiles(sourceFolder);
fs.appendFileSync(outputFile, allContent, 'utf-8');

console.log(`✅ Code extracted to: ${outputFile}`);
